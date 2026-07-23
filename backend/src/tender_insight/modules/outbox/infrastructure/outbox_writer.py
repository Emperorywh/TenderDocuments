"""outbox 事务写入 SQLAlchemy 适配器（D-008）。

在当前业务会话内暂存一条 outbox_events INSERT，不在内部提交：事件随业务事务一起
提交或回滚（SPEC.md 第 5.2 节）。这保证“业务事务回滚时事件同步回滚”，不会留下
孤儿事件指向已回滚的业务变更。
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from tender_insight.modules.outbox.application import (
    OutboxDeliveryStatus,
    OutboxEvent,
)
from tender_insight.modules.outbox.infrastructure.models import OutboxEventModel


class SqlAlchemyOutboxWriter:
    """事务内 outbox 写入适配器；不在内部提交。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def write(self, event: OutboxEvent) -> None:
        """在当前会话暂存一条 PENDING 事件（随业务事务提交/回滚）。"""
        self._session.add(
            OutboxEventModel(
                id=uuid4(),
                event_id=event.event_id,
                event_type=event.event_type,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                payload=event.payload,
                delivery_status=OutboxDeliveryStatus.PENDING.value,
                attempts=0,
            )
        )
