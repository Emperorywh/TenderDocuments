"""Broker 投递与确认测试（D-010 独立验证）。

验证 Celery 投递适配器与“领取→投递→确认 DELIVERED”编排：投递成功后数据库记录
确认状态（DELIVERED）；投递失败抛稳定 OutboxDeliveryError 并由调用方回滚，事件保持
PENDING 待 D-011 补偿重投。

Celery/Redis 是投递通道（非事实来源）；本机无 Celery worker，适配器以注入的伪 Celery
应用验证投递逻辑，真实 Celery 投递验证待 Docker 就绪补充（与既有 SQLite↔PG 诚实记录
一致）。领域/应用层不导入 Celery/Redis SDK，仅依赖 OutboxBroker 端口。
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from tender_insight.modules.outbox.application import (
    OutboxBroker,
    OutboxDeliveryError,
    OutboxEventClaim,
)
from tender_insight.modules.outbox.infrastructure.celery_broker import CeleryOutboxBroker
from tender_insight.modules.outbox.infrastructure.models import OutboxEventModel
from tender_insight.modules.outbox.infrastructure.outbox_delivery import (
    DispatchOutcome,
    dispatch_outbox_events,
    mark_event_delivered,
)


def _claim(event_id: str = "evt-1") -> OutboxEventClaim:
    return OutboxEventClaim(
        event_id=event_id,
        event_type="analysis.task.dispatched",
        aggregate_type="analysis_task",
        aggregate_id="task-1",
        payload={"task_id": "task-1", "queue": "parse"},
    )


class _FakeBroker:
    """内存伪 broker：记录投递事件，可配置在第 N 条投递失败。"""

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.delivered: list[OutboxEventClaim] = []
        self._fail_on = fail_on

    def deliver(self, claim: OutboxEventClaim) -> None:
        if self._fail_on is not None and claim.event_id == self._fail_on:
            raise OutboxDeliveryError(f"模拟投递失败: {claim.event_id}")
        self.delivered.append(claim)


def _seed(
    session: Session,
    *,
    event_id: str,
    status: str = "PENDING",
    created_at: datetime | None = None,
) -> None:
    session.add(
        OutboxEventModel(
            id=uuid4(),
            event_id=event_id,
            event_type="analysis.task.dispatched",
            aggregate_type="analysis_task",
            aggregate_id="task-1",
            payload={"task_id": "task-1"},
            delivery_status=status,
            attempts=0,
            created_at=created_at or datetime.now(UTC),
        )
    )


def test_broker_port_is_pure() -> None:
    """端口模块（application）不导入 Celery/Redis SDK（A-006 守护：AST 导入扫描）。

    以 AST 导入扫描判定（与权威 dependency_rules 一致），避免 docstring/注释中
    出现 “Celery/Redis” 字样造成字符串误判。
    """
    import tender_insight.modules.outbox.application as app_mod
    from tests.architecture.dependency_rules import scan_imports

    imports = scan_imports(Path(app_mod.__file__))
    roots = {mod.split(".")[0] for mod in imports}
    assert "celery" not in roots
    assert "redis" not in roots
    assert "kombu" not in roots
    # OutboxBroker 为 Protocol（结构性满足由下面的适配器与伪 broker 验证）。
    assert hasattr(app_mod, "OutboxBroker")


def test_celery_broker_implements_protocol() -> None:
    """CeleryOutboxBroker 满足 OutboxBroker 端口（结构性）。"""
    broker: OutboxBroker = CeleryOutboxBroker(MagicMock(), "worker.outbox.consume")  # type: ignore[assignment]
    assert hasattr(broker, "deliver")


def test_celery_broker_sends_task_with_envelope() -> None:
    """适配器以事件消息信封调用 Celery send_task（event_id 作为幂等键随消息传递）。"""
    fake_app = MagicMock()
    broker = CeleryOutboxBroker(fake_app, "worker.outbox.consume")

    broker.deliver(_claim("evt-send"))

    fake_app.send_task.assert_called_once()
    args, kwargs = fake_app.send_task.call_args
    assert args[0] == "worker.outbox.consume"
    envelope = kwargs["kwargs"]
    assert envelope["event_id"] == "evt-send"
    assert envelope["event_type"] == "analysis.task.dispatched"
    assert envelope["payload"] == {"task_id": "task-1", "queue": "parse"}


def test_celery_broker_wraps_failure_as_outbox_delivery_error() -> None:
    """底层异常归一为稳定 OutboxDeliveryError（便于编排统一回滚与补偿分类）。"""
    fake_app = MagicMock()
    fake_app.send_task.side_effect = RuntimeError("broker 不可达")
    broker = CeleryOutboxBroker(fake_app, "worker.outbox.consume")

    with pytest.raises(OutboxDeliveryError) as exc_info:
        broker.deliver(_claim("evt-fail"))

    assert exc_info.value.code == "OUTBOX_DELIVERY_FAILED"
    assert exc_info.value.http_status == 502
    assert "evt-fail" in exc_info.value.detail


def test_dispatch_marks_events_delivered_on_success(db_session: Session) -> None:
    """核心验证：投递成功后数据库记录确认状态 DELIVERED。"""
    base = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
    _seed(db_session, event_id="evt-a", created_at=base)
    _seed(db_session, event_id="evt-b", created_at=base.replace(minute=1))
    db_session.commit()
    broker = _FakeBroker()

    outcome = dispatch_outbox_events(db_session, broker, batch_size=10)
    db_session.commit()

    assert outcome.delivered == 2
    assert outcome.failed == 0
    assert [c.event_id for c in broker.delivered] == ["evt-a", "evt-b"]
    rows = db_session.query(OutboxEventModel).order_by(OutboxEventModel.event_id).all()
    assert all(r.delivery_status == "DELIVERED" for r in rows)
    # attempts 记录投递尝试（成功计一次）；last_attempt_at 刷新。
    assert all(r.attempts == 1 for r in rows)
    assert all(r.last_attempt_at is not None for r in rows)


def test_dispatch_respects_batch_size(db_session: Session) -> None:
    """batch_size 限制单轮领取与投递数量。"""
    base = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
    for i in range(5):
        _seed(db_session, event_id=f"evt-{i}", created_at=base.replace(minute=i))
    db_session.commit()
    broker = _FakeBroker()

    outcome = dispatch_outbox_events(db_session, broker, batch_size=2)
    db_session.commit()

    assert outcome.delivered == 2
    # 其余仍为 PENDING，待下轮投递。
    pending = (
        db_session.query(OutboxEventModel)
        .filter_by(delivery_status="PENDING")
        .count()
    )
    assert pending == 3


def test_dispatch_only_processes_pending(db_session: Session) -> None:
    """仅 PENDING 被投递确认；已 DELIVERED/FAILED 不重复投递。"""
    t = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
    _seed(db_session, event_id="pending", status="PENDING", created_at=t)
    _seed(db_session, event_id="delivered", status="DELIVERED", created_at=t)
    _seed(db_session, event_id="failed", status="FAILED", created_at=t)
    db_session.commit()
    broker = _FakeBroker()

    outcome = dispatch_outbox_events(db_session, broker, batch_size=10)
    db_session.commit()

    assert outcome.delivered == 1
    assert outcome.failed == 0
    assert [c.event_id for c in broker.delivered] == ["pending"]


def test_dispatch_returns_zero_when_empty(db_session: Session) -> None:
    """无 PENDING 事件时投递 0 条（Scheduler 空轮询）。"""
    broker = _FakeBroker()

    outcome = dispatch_outbox_events(db_session, broker, batch_size=10)

    assert outcome == DispatchOutcome(delivered=0, failed=0)
    assert broker.delivered == []


def test_dispatch_marks_failed_without_rolling_back_success(db_session: Session) -> None:
    """投递失败标记 FAILED（不回滚已成功条目）；成功条目 DELIVERED、失败条目 FAILED。

    逐条独立结算：evt-ok 投递成功 → DELIVERED，evt-bad 投递失败 → FAILED(attempts=1)，
    失败条目由 D-011 补偿按退避重新入队后下轮重投。
    """
    base = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
    _seed(db_session, event_id="evt-ok", created_at=base)
    _seed(db_session, event_id="evt-bad", created_at=base.replace(minute=1))
    db_session.commit()
    broker = _FakeBroker(fail_on="evt-bad")

    outcome = dispatch_outbox_events(db_session, broker, batch_size=10)
    db_session.commit()

    assert outcome.delivered == 1
    assert outcome.failed == 1
    ok_row = db_session.query(OutboxEventModel).filter_by(event_id="evt-ok").one()
    bad_row = db_session.query(OutboxEventModel).filter_by(event_id="evt-bad").one()
    assert ok_row.delivery_status == "DELIVERED"
    assert bad_row.delivery_status == "FAILED"
    assert bad_row.attempts == 1
    assert bad_row.last_attempt_at is not None


def test_mark_delivered_is_idempotent_by_event_id(db_session: Session) -> None:
    """mark_event_delivered 按 event_id 定位；重复调用累加 attempts（对账用）。"""
    _seed(db_session, event_id="evt-mark")
    db_session.commit()

    mark_event_delivered(db_session, "evt-mark")
    mark_event_delivered(db_session, "evt-mark")
    db_session.commit()

    row = db_session.query(OutboxEventModel).filter_by(event_id="evt-mark").one()
    assert row.delivery_status == "DELIVERED"
    assert row.attempts == 2
