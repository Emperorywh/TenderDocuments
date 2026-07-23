"""outbox 事件领取（D-009）。

Scheduler 以 SELECT ... FOR UPDATE SKIP LOCKED 领取 PENDING 事件（SPEC.md 第 5.2 节、
第 11.3 节）：同一行被一个 Scheduler 锁定后，并发 Scheduler 的领取查询跳过该行，
从而同一事件在并发领取下只被一个 Scheduler 取得（验证：两个 Scheduler 并发时事件
只被一个领取）。

PostgreSQL 是生产唯一事实来源（ADR-004），SKIP LOCKED 提供行级排他领取；SQLite 作为
测试替代库不支持该子句，SQLAlchemy 在 SQLite 方言下会省略 FOR UPDATE（仅作为可运行的
领取逻辑验证，并发排他由 PostgreSQL 保证）。

行锁在当前事务提交/回滚前一直持有：Scheduler 领取→投递（D-010）→确认 DELIVERED
（D-010）在同一事务内完成，确保并发 Scheduler 不会重复领取同一事件。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tender_insight.modules.outbox.application import (
    OutboxDeliveryStatus,
    OutboxEventClaim,
)
from tender_insight.modules.outbox.infrastructure.models import OutboxEventModel


def claim_pending_events(session: Session, *, limit: int = 10) -> list[OutboxEventClaim]:
    """领取至多 limit 条 PENDING 事件（按创建时间顺序），持有行锁直至事务结束。

    返回的事件消息信封供 Scheduler 投递到 Celery（D-010）；行锁在当前事务结束前
    持续持有，使并发 Scheduler 不会重复领取同一事件。领取本身不修改事件状态：
    投递成功后由确认步骤标记 DELIVERED（D-010），失败由补偿重投（D-011）处理。
    """
    stmt = (
        select(OutboxEventModel)
        .where(OutboxEventModel.delivery_status == OutboxDeliveryStatus.PENDING.value)
        .order_by(OutboxEventModel.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    rows = session.execute(stmt).scalars().all()
    return [
        OutboxEventClaim(
            event_id=row.event_id,
            event_type=row.event_type,
            aggregate_type=row.aggregate_type,
            aggregate_id=row.aggregate_id,
            payload=row.payload,
        )
        for row in rows
    ]
