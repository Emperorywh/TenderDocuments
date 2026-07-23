"""outbox 投递与确认编排（D-010、D-011）。

Scheduler 投递步：在同一事务内领取 PENDING 事件 → 经 OutboxBroker 投递到
Celery/Redis → 成功确认 DELIVERED、失败标记 FAILED（attempts 自增、last_attempt_at
刷新）。随后由调用方提交（SPEC.md 第 5.2 节、第 11.3 节）。行锁从领取持有至提交，
确保并发 Scheduler 不会重复投递同一事件（D-009）。

投递成功后事件落库为 DELIVERED（验证：投递成功后数据库记录确认状态）；投递失败
标记 FAILED，由 D-011 补偿按指数退避重新入队（requeue_failed_events）后下轮重新
投递。outbox 允许重复投递，Worker 必须幂等消费（SPEC.md 第 11.3 节）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import func, update

from tender_insight.modules.outbox.application import (
    OutboxBroker,
    OutboxDeliveryError,
)
from tender_insight.modules.outbox.infrastructure.claim_events import (
    claim_pending_events,
)
from tender_insight.modules.outbox.infrastructure.models import OutboxEventModel

if TYPE_CHECKING:  # 仅类型注解用，避免运行期 ORM 耦合到应用编排签名。
    from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DispatchOutcome:
    """一轮投递的结果计数：成功确认 DELIVERED 与失败标记 FAILED 各若干。

    逐条独立结算（不因单条失败回滚已成功投递的条目），失败条目由补偿重投（D-011）。
    """

    delivered: int
    failed: int


def mark_event_delivered(session: Session, event_id: str) -> None:
    """确认一条事件投递成功：DELIVERED + attempts 自增 + last_attempt_at 刷新。

    attempts 记录投递尝试次数（成功亦计一次），供 D-011 退避与对账使用。
    按 event_id（业务唯一键）定位行；不在内部提交，随调度事务一起持久化。
    """
    session.execute(
        update(OutboxEventModel)
        .where(OutboxEventModel.event_id == event_id)
        .values(
            delivery_status="DELIVERED",
            attempts=OutboxEventModel.attempts + 1,
            last_attempt_at=func.now(),
        )
    )


def mark_event_failed(session: Session, event_id: str) -> None:
    """标记一条事件投递失败：FAILED + attempts 自增 + last_attempt_at 刷新。

    保留 attempts/last_attempt_at 供 D-011 补偿计算退避与重新入队；不在内部提交。
    """
    session.execute(
        update(OutboxEventModel)
        .where(OutboxEventModel.event_id == event_id)
        .values(
            delivery_status="FAILED",
            attempts=OutboxEventModel.attempts + 1,
            last_attempt_at=func.now(),
        )
    )


def dispatch_outbox_events(
    session: Session,
    broker: OutboxBroker,
    *,
    batch_size: int = 10,
) -> DispatchOutcome:
    """Scheduler 投递步：领取→投递→逐条确认 DELIVERED/FAILED，返回本轮结果。

    在调用方事务内执行（行锁从领取持有至提交）。逐条投递并结算：成功 mark_event_
    delivered，失败捕获 OutboxDeliveryError 后 mark_event_failed（不抛出、不回滚已
    成功条目），失败条目由 D-011 补偿按退避重新入队后下轮重投。本函数不提交。
    """
    claims = claim_pending_events(session, limit=batch_size)
    delivered = 0
    failed = 0
    for claim in claims:
        try:
            broker.deliver(claim)
        except OutboxDeliveryError:
            mark_event_failed(session, claim.event_id)
            failed += 1
        else:
            mark_event_delivered(session, claim.event_id)
            delivered += 1
    return DispatchOutcome(delivered=delivered, failed=failed)
