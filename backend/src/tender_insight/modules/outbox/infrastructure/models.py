"""outbox 模块 ORM Model（D-007）。

outbox_events 表：事务性事件记录。业务变更与事件写入同一事务（SPEC.md 第 5.2 节），
由 Scheduler 领取投递。event_id 为业务事件唯一键，保证相同业务事件不产生重复行
（幂等投递的基础，SPEC.md 第 11.3 节）。payload 为事件消息信封（稳定 ID 与参数），
不是正式领域模型整体，故以 JSON 承载（SPEC.md 第 7.2 节）。

delivery_status 表达投递进度（PENDING/DELIVERED/FAILED），与业务状态分离；Outbox
允许重复投递，Worker 必须幂等消费。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from tender_insight.shared.orm import Base, TimestampMixin


class OutboxEventModel(Base, TimestampMixin):
    """outbox_events 表：事务性事件记录。

    event_id 在全表唯一，使重复业务事件不产生重复投递；payload 为消息信封
    （非领域模型整体）。delivery_status 与 attempts 支持补偿重投（D-011）。
    """

    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    # 业务事件唯一键：幂等投递基础（SPEC.md 第 11.3 节）。
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    # 事件类型（如 analysis.task.dispatched）。
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # 聚合类型与 ID（事件关联的业务实体，便于按聚合查询）。
    aggregate_type: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # 事件消息信封（稳定 ID 与参数）；非领域模型整体。
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    # 投递状态：PENDING/DELIVERED/FAILED，与业务状态分离。
    delivery_status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
