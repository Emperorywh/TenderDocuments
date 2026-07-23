"""Scheduler 事件领取测试（D-009 独立验证）。

验证带行锁的 PENDING 事件领取：
- 功能行为（顺序、limit、仅 PENDING、消息信封回读）在 SQLite 上可运行验证；
- 并发排他性（“两个 Scheduler 并发时事件只被一个领取”）由 SELECT ... FOR UPDATE
  SKIP LOCKED 提供，该子句在生产 PostgreSQL 上具行级排他语义。SQLite 方言会省略
  FOR UPDATE（仅作可运行的领取逻辑验证），故并发排他性以“编译到 PostgreSQL 方言的
  SQL 含 FOR UPDATE 与 SKIP LOCKED”作结构性证明；真实 PostgreSQL 并发领取验证待
  Docker 就绪补充（与 B-001/C-002 等既有 SQLite↔PG 诚实记录一致）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from tender_insight.modules.outbox.application import (
    OutboxDeliveryStatus,
    OutboxEventClaim,
)
from tender_insight.modules.outbox.infrastructure.claim_events import (
    claim_pending_events,
)
from tender_insight.modules.outbox.infrastructure.models import OutboxEventModel


def _make_row(
    *,
    event_id: str,
    status: OutboxDeliveryStatus = OutboxDeliveryStatus.PENDING,
    created_at: datetime | None = None,
    payload: dict | None = None,
) -> OutboxEventModel:
    """构造一条 outbox 事件行（created_at 可显式指定以控制领取顺序）。"""
    return OutboxEventModel(
        id=uuid4(),
        event_id=event_id,
        event_type="analysis.task.dispatched",
        aggregate_type="analysis_task",
        aggregate_id="task-1",
        payload=payload if payload is not None else {"task_id": "task-1"},
        delivery_status=status.value,
        attempts=0,
        # 显式 created_at 使领取顺序在测试中确定（SQLite 的 now() 精度不足以区分）。
        created_at=created_at or datetime.now(UTC),
    )


def test_claim_returns_pending_events_ordered_by_created_at(db_session: Session) -> None:
    """领取返回 PENDING 事件，按 created_at 升序（FIFO 投递顺序）。"""
    t0 = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
    t1 = datetime(2026, 7, 23, 10, 1, tzinfo=UTC)
    t2 = datetime(2026, 7, 23, 10, 2, tzinfo=UTC)
    # 故意乱序插入，验证领取按 created_at 而非插入顺序排序。
    for row in (
        _make_row(event_id="evt-2", created_at=t1),
        _make_row(event_id="evt-1", created_at=t0),
        _make_row(event_id="evt-3", created_at=t2),
    ):
        db_session.add(row)
    db_session.commit()

    claims = claim_pending_events(db_session, limit=10)

    assert [c.event_id for c in claims] == ["evt-1", "evt-2", "evt-3"]


def test_claim_respects_limit(db_session: Session) -> None:
    """limit 限制单次领取数量（Scheduler 批量领取受控）。"""
    base = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
    for i in range(5):
        db_session.add(_make_row(event_id=f"evt-{i}", created_at=base))
    db_session.commit()

    claims = claim_pending_events(db_session, limit=2)

    assert len(claims) == 2


def test_claim_excludes_non_pending(db_session: Session) -> None:
    """仅领取 PENDING；DELIVERED 与 FAILED 不被重复领取。"""
    t = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
    db_session.add(_make_row(event_id="pending", status=OutboxDeliveryStatus.PENDING, created_at=t))
    db_session.add(
        _make_row(event_id="delivered", status=OutboxDeliveryStatus.DELIVERED, created_at=t)
    )
    db_session.add(_make_row(event_id="failed", status=OutboxDeliveryStatus.FAILED, created_at=t))
    db_session.commit()

    claims = claim_pending_events(db_session, limit=10)

    assert [c.event_id for c in claims] == ["pending"]


def test_claim_returns_empty_when_no_pending(db_session: Session) -> None:
    """无 PENDING 事件时领取返回空列表（Scheduler 空轮询）。"""
    db_session.add(
        _make_row(event_id="delivered", status=OutboxDeliveryStatus.DELIVERED)
    )
    db_session.commit()

    assert claim_pending_events(db_session, limit=10) == []


def test_claim_payload_passthrough(db_session: Session) -> None:
    """领取返回的消息信封完整回读 payload（稳定 ID + 参数，非领域模型整体）。"""
    payload = {"task_id": "task-9", "queue": "parse", "attempt": 1}
    db_session.add(_make_row(event_id="evt-payload", payload=payload))
    db_session.commit()

    claims = claim_pending_events(db_session, limit=10)

    assert len(claims) == 1
    claim = claims[0]
    assert claim.event_id == "evt-payload"
    assert claim.event_type == "analysis.task.dispatched"
    assert claim.aggregate_type == "analysis_task"
    assert claim.aggregate_id == "task-1"
    assert claim.payload == payload


def test_claim_does_not_mutate_event(db_session: Session) -> None:
    """领取不修改事件状态（非破坏性领取）；确认 DELIVERED 属 D-010 职责。"""
    db_session.add(_make_row(event_id="evt-noop"))
    db_session.commit()

    claim_pending_events(db_session, limit=10)
    db_session.commit()

    row = db_session.query(OutboxEventModel).filter_by(event_id="evt-noop").one()
    assert row.delivery_status == OutboxDeliveryStatus.PENDING.value
    assert row.attempts == 0


def test_claim_compiles_to_for_update_skip_locked_on_postgres() -> None:
    """并发排他性结构性证明：领取语句编译到 PostgreSQL 含 FOR UPDATE SKIP LOCKED。

    生产 PostgreSQL 以行级排他锁保证“两个 Scheduler 并发时事件只被一个领取”：
    一个 Scheduler 锁定行后，并发 Scheduler 的 SKIP LOCKED 跳过该行。SQLite 方言
    省略 FOR UPDATE（见模块 docstring 的诚实记录），故以 PostgreSQL 方言编译验证。
    """
    captured_session = MagicMock()
    # session.execute(stmt).scalars().all() → 空列表（仅用于捕获 stmt）。
    captured_session.execute.return_value.scalars.return_value.all.return_value = []

    claim_pending_events(captured_session, limit=8)

    stmt = captured_session.execute.call_args[0][0]
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
    assert "SKIP LOCKED" in sql


def test_outbox_event_claim_is_immutable_envelope() -> None:
    """领取返回值为不可变消息信封：仅暴露稳定 ID 与参数，不可被篡改。"""
    import dataclasses

    claim = OutboxEventClaim(
        event_id="evt-1",
        event_type="analysis.task.dispatched",
        aggregate_type="analysis_task",
        aggregate_id="task-1",
        payload={"task_id": "task-1"},
    )
    assert dataclasses.is_dataclass(claim)
    # frozen dataclass：赋值抛 FrozenInstanceError，防止下游误改消息信封。
    try:
        claim.event_id = "tampered"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        pass
    else:  # pragma: no cover - 防御：未冻结则测试失败
        raise AssertionError("OutboxEventClaim 必须为不可变 frozen dataclass")
    assert claim.event_id == "evt-1"
