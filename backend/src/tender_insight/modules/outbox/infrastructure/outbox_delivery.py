"""outbox 投递与确认编排（D-010）。

Scheduler 投递步：在同一事务内领取 PENDING 事件 → 经 OutboxBroker 投递到
Celery/Redis → 确认 DELIVERED，随后由调用方提交（SPEC.md 第 5.2 节、第 11.3 节）。
行锁从领取持有至提交，确保并发 Scheduler 不会重复投递同一事件（D-009）。

投递成功后事件落库为 DELIVERED（验证：投递成功后数据库记录确认状态）；投递失败
抛 OutboxDeliveryError，调用方回滚事务使事件保持 PENDING，由 D-011 补偿按指数
退避重新投递。outbox 允许重复投递，Worker 必须幂等消费（SPEC.md 第 11.3 节）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, update

from tender_insight.modules.outbox.application import OutboxBroker
from tender_insight.modules.outbox.infrastructure.claim_events import (
    claim_pending_events,
)
from tender_insight.modules.outbox.infrastructure.models import OutboxEventModel

if TYPE_CHECKING:  # 仅类型注解用，避免运行期 ORM 耦合到应用编排签名。
    from sqlalchemy.orm import Session


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


def dispatch_outbox_events(
    session: Session,
    broker: OutboxBroker,
    *,
    batch_size: int = 10,
) -> int:
    """Scheduler 投递步：领取→投递→确认 DELIVERED，返回本轮投递条数。

    在调用方事务内执行（行锁从领取持有至提交）。逐条投递并确认：任一投递抛
    OutboxDeliveryError 即向上抛出，调用方回滚使本轮事件保持 PENDING（已投递到
    broker 的部分由幂等 Worker 去重），由 D-011 补偿重投。本函数不提交。
    """
    claims = claim_pending_events(session, limit=batch_size)
    for claim in claims:
        # 投递失败抛 OutboxDeliveryError，终止本轮并交由调用方回滚。
        broker.deliver(claim)
        mark_event_delivered(session, claim.event_id)
    return len(claims)
