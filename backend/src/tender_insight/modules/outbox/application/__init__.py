"""outbox 应用层端口（D-008）。

定义事务内事件写入端口 OutboxWriter 与事件值对象 OutboxEvent。端口刻意保持纯
（仅标准库），使 application/domain 不依赖 ORM；适配器在业务事务内暂存 INSERT，
不在内部提交，从而事件与业务变更同事务提交或回滚（SPEC.md 第 5.2 节）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class OutboxDeliveryStatus(StrEnum):
    """事件投递状态（与业务状态分离）。"""

    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class OutboxEvent:
    """待写入的事务事件值对象。

    event_id 为业务事件唯一键（幂等投递基础）；payload 为消息信封（稳定 ID 与参数），
    不承载正式领域模型整体（SPEC.md 第 7.2 节）。
    """

    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict


class OutboxWriter(Protocol):
    """事务内事件写入端口。

    实现必须在当前业务会话内暂存事件 INSERT，且**不在内部提交**：事件随业务事务
    一起提交或回滚（SPEC.md 第 5.2 节“同一模块聚合修改和 OutboxEvent 在同一事务提交”）。
    """

    def write(self, event: OutboxEvent) -> None:
        """在当前事务内写入一条事件（不提交）。"""
        ...
