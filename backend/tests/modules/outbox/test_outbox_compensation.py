"""outbox 投递补偿测试（D-011 独立验证）。

验证失败退避与重新投递规则：投递失败的事件标记 FAILED，按指数退避等待后由补偿
重新入队（FAILED→PENDING），下轮 dispatch 重新投递。超过最大尝试次数的 FAILED
事件成为死信，不再自动重投。核心验证：模拟 Broker 失败后事件最终重新投递。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from tender_insight.modules.outbox.application import (
    OutboxDeliveryError,
    OutboxEventClaim,
)
from tender_insight.modules.outbox.domain.backoff import exponential_backoff_seconds
from tender_insight.modules.outbox.infrastructure.models import OutboxEventModel
from tender_insight.modules.outbox.infrastructure.outbox_compensation import (
    requeue_failed_events,
)
from tender_insight.modules.outbox.infrastructure.outbox_delivery import (
    dispatch_outbox_events,
)

# 退避参数（测试用小值；生产由配置注入）。
_BASE = 1.0
_FACTOR = 2.0
_MAX_SECONDS = 60.0
_MAX_ATTEMPTS = 5


def test_backoff_grows_exponentially_and_caps() -> None:
    """指数退避：base * factor^(attempts-1)，封顶 max_seconds。"""
    assert exponential_backoff_seconds(1, base_seconds=_BASE, factor=_FACTOR, max_seconds=_MAX_SECONDS) == 1.0
    assert exponential_backoff_seconds(2, base_seconds=_BASE, factor=_FACTOR, max_seconds=_MAX_SECONDS) == 2.0
    assert exponential_backoff_seconds(3, base_seconds=_BASE, factor=_FACTOR, max_seconds=_MAX_SECONDS) == 4.0
    assert exponential_backoff_seconds(4, base_seconds=_BASE, factor=_FACTOR, max_seconds=_MAX_SECONDS) == 8.0
    # 封顶：理论值 1024 > 60。
    assert exponential_backoff_seconds(11, base_seconds=_BASE, factor=_FACTOR, max_seconds=_MAX_SECONDS) == 60.0


def test_backoff_zero_when_no_attempts() -> None:
    """尚未发生失败（attempts<1）立即可重投，退避为 0。"""
    assert exponential_backoff_seconds(0, base_seconds=_BASE, factor=_FACTOR, max_seconds=_MAX_SECONDS) == 0.0


def _seed_failed(
    session: Session,
    *,
    event_id: str,
    attempts: int,
    last_attempt_at: datetime,
) -> None:
    """构造一条 FAILED 事件，显式指定 attempts 与 last_attempt_at（确定性退避判定）。"""
    session.add(
        OutboxEventModel(
            id=uuid4(),
            event_id=event_id,
            event_type="analysis.task.dispatched",
            aggregate_type="analysis_task",
            aggregate_id="task-1",
            payload={"task_id": "task-1"},
            delivery_status="FAILED",
            attempts=attempts,
            last_attempt_at=last_attempt_at,
        )
    )


def test_requeue_resets_failed_to_pending_after_backoff(session_factory) -> None:
    """退避已过的 FAILED 事件重新入队为 PENDING（下轮 dispatch 重新投递）。"""
    session = session_factory()
    try:
        # 1 次失败 → 退避 1s；last_attempt_at 在 5s 前，退避已过。
        failed_at = datetime(2026, 7, 23, 10, 0, 0, tzinfo=UTC)
        _seed_failed(session, event_id="evt-1", attempts=1, last_attempt_at=failed_at)
        session.commit()

        now = failed_at + timedelta(seconds=5)
        requeued = requeue_failed_events(
            session,
            now=now,
            base_seconds=_BASE,
            factor=_FACTOR,
            max_seconds=_MAX_SECONDS,
            max_attempts=_MAX_ATTEMPTS,
        )
        session.commit()

        assert requeued == 1
        row = session.query(OutboxEventModel).filter_by(event_id="evt-1").one()
        assert row.delivery_status == "PENDING"
        # attempts 保留（退避跨重试延续增长）。
        assert row.attempts == 1
    finally:
        session.close()


def test_requeue_keeps_failed_within_backoff_window(session_factory) -> None:
    """退避未过的 FAILED 事件保持 FAILED（避免对 broker 热轮询）。"""
    session = session_factory()
    try:
        failed_at = datetime(2026, 7, 23, 10, 0, 0, tzinfo=UTC)
        _seed_failed(session, event_id="evt-1", attempts=1, last_attempt_at=failed_at)
        session.commit()

        # 仅过 0.5s < 1s 退避。
        now = failed_at + timedelta(seconds=0.5)
        requeued = requeue_failed_events(
            session,
            now=now,
            base_seconds=_BASE,
            factor=_FACTOR,
            max_seconds=_MAX_SECONDS,
            max_attempts=_MAX_ATTEMPTS,
        )
        session.commit()

        assert requeued == 0
        row = session.query(OutboxEventModel).filter_by(event_id="evt-1").one()
        assert row.delivery_status == "FAILED"
    finally:
        session.close()


def test_requeue_dead_letter_at_max_attempts(session_factory) -> None:
    """超过 max_attempts 的 FAILED 事件成为死信，不再自动重投（需人工处理）。"""
    session = session_factory()
    try:
        failed_at = datetime(2026, 7, 23, 10, 0, 0, tzinfo=UTC)
        _seed_failed(session, event_id="evt-dead", attempts=_MAX_ATTEMPTS, last_attempt_at=failed_at)
        session.commit()

        now = failed_at + timedelta(seconds=999)
        requeued = requeue_failed_events(
            session,
            now=now,
            base_seconds=_BASE,
            factor=_FACTOR,
            max_seconds=_MAX_SECONDS,
            max_attempts=_MAX_ATTEMPTS,
        )
        session.commit()

        assert requeued == 0
        row = session.query(OutboxEventModel).filter_by(event_id="evt-dead").one()
        assert row.delivery_status == "FAILED"
    finally:
        session.close()


def test_requeue_only_affects_failed(session_factory) -> None:
    """仅 FAILED 被重新入队；PENDING/DELIVERED 不受影响。"""
    session = session_factory()
    try:
        t = datetime(2026, 7, 23, 10, 0, 0, tzinfo=UTC)
        _seed_failed(session, event_id="failed", attempts=1, last_attempt_at=t)
        session.add(
            OutboxEventModel(
                id=uuid4(),
                event_id="pending",
                event_type="analysis.task.dispatched",
                aggregate_type="analysis_task",
                aggregate_id="task-1",
                payload={"task_id": "task-1"},
                delivery_status="PENDING",
                attempts=0,
            )
        )
        session.add(
            OutboxEventModel(
                id=uuid4(),
                event_id="delivered",
                event_type="analysis.task.dispatched",
                aggregate_type="analysis_task",
                aggregate_id="task-1",
                payload={"task_id": "task-1"},
                delivery_status="DELIVERED",
                attempts=1,
            )
        )
        session.commit()

        now = t + timedelta(seconds=5)
        requeued = requeue_failed_events(
            session,
            now=now,
            base_seconds=_BASE,
            factor=_FACTOR,
            max_seconds=_MAX_SECONDS,
            max_attempts=_MAX_ATTEMPTS,
        )
        session.commit()

        assert requeued == 1
        assert session.query(OutboxEventModel).filter_by(event_id="pending").one().delivery_status == "PENDING"
        assert (
            session.query(OutboxEventModel).filter_by(event_id="delivered").one().delivery_status
            == "DELIVERED"
        )
    finally:
        session.close()


class _FailThenSucceedBroker:
    """前 fail_times 次投递抛 OutboxDeliveryError，之后成功（模拟 broker 恢复）。"""

    def __init__(self, fail_times: int) -> None:
        self._fail_times = fail_times
        self.delivered: list[OutboxEventClaim] = []

    def deliver(self, claim: OutboxEventClaim) -> None:
        if self._fail_times > 0:
            self._fail_times -= 1
            raise OutboxDeliveryError(f"模拟投递失败: {claim.event_id}")
        self.delivered.append(claim)


def test_full_retry_cycle_eventually_redelivered(session_factory) -> None:
    """核心验证：模拟 Broker 失败后事件最终重新投递。

    流程：PENDING → dispatch(broker 失败) → FAILED → 退避过后 requeue → PENDING →
    dispatch(broker 恢复) → DELIVERED。
    """
    session = session_factory()
    try:
        session.add(
            OutboxEventModel(
                id=uuid4(),
                event_id="evt-cycle",
                event_type="analysis.task.dispatched",
                aggregate_type="analysis_task",
                aggregate_id="task-1",
                payload={"task_id": "task-1"},
                delivery_status="PENDING",
                attempts=0,
            )
        )
        session.commit()
        broker = _FailThenSucceedBroker(fail_times=1)

        # 第 1 轮：broker 失败 → 事件标记 FAILED。
        outcome1 = dispatch_outbox_events(session, broker, batch_size=10)
        session.commit()
        assert outcome1.failed == 1
        failed_row = session.query(OutboxEventModel).filter_by(event_id="evt-cycle").one()
        assert failed_row.delivery_status == "FAILED"
        assert failed_row.attempts == 1
        last_attempt = failed_row.last_attempt_at
        assert last_attempt is not None

        # 退避未过：requeue 不重新入队。
        if last_attempt.tzinfo is None:
            last_attempt = last_attempt.replace(tzinfo=UTC)
        requeued_early = requeue_failed_events(
            session,
            now=last_attempt + timedelta(seconds=0.1),
            base_seconds=_BASE,
            factor=_FACTOR,
            max_seconds=_MAX_SECONDS,
            max_attempts=_MAX_ATTEMPTS,
        )
        assert requeued_early == 0

        # 退避已过：requeue 重新入队为 PENDING。
        requeued = requeue_failed_events(
            session,
            now=last_attempt + timedelta(seconds=10),
            base_seconds=_BASE,
            factor=_FACTOR,
            max_seconds=_MAX_SECONDS,
            max_attempts=_MAX_ATTEMPTS,
        )
        session.commit()
        assert requeued == 1
        assert (
            session.query(OutboxEventModel).filter_by(event_id="evt-cycle").one().delivery_status
            == "PENDING"
        )

        # 第 2 轮：broker 恢复 → 事件投递成功 DELIVERED。
        outcome2 = dispatch_outbox_events(session, broker, batch_size=10)
        session.commit()
        assert outcome2.delivered == 1
        assert (
            session.query(OutboxEventModel).filter_by(event_id="evt-cycle").one().delivery_status
            == "DELIVERED"
        )
        assert broker.delivered[0].event_id == "evt-cycle"
    finally:
        session.close()
