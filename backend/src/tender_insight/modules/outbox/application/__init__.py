"""outbox 应用层端口（D-008、D-010）。

定义事务内事件写入端口 OutboxWriter 与事件值对象 OutboxEvent。端口刻意保持纯
（仅标准库），使 application/domain 不依赖 ORM；适配器在业务事务内暂存 INSERT，
不在内部提交，从而事件与业务变更同事务提交或回滚（SPEC.md 第 5.2 节）。

D-010 增加投递端口 OutboxBroker（将已领取事件投递到 Celery/Redis，非事实来源）
与稳定错误 OutboxDeliveryError，供 Scheduler 领取→投递→确认编排使用。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from tender_insight.shared.domain_error import DomainError
from tender_insight.shared.error_codes import ErrorCode


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


@dataclass(frozen=True)
class OutboxEventClaim:
    """已领取事件的消息信封（D-009）。

    Scheduler 带行锁领取 PENDING 事件后，仅向投递通道暴露稳定 ID 与消息信封，
    不承载正式领域模型整体（SPEC.md 第 7.2 节）。event_id 为业务事件唯一键，
    供下游 Worker 幂等消费。
    """

    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    payload: dict


class OutboxDeliveryError(DomainError):
    """事件投递失败（broker 端错误，如 Celery/Redis 不可达）。

    携带稳定 code 供 D-011 补偿重投分类（与可重试错误目录 D-019 协作）。
    投递失败时调用方回滚事务，事件保持 PENDING，由 Scheduler 下轮或补偿重投。
    """

    code = ErrorCode.OUTBOX_DELIVERY_FAILED.value
    http_status = 502
    title = "事件投递失败"


class OutboxBroker(Protocol):
    """事件投递端口：将已领取事件投递到 Celery/Redis（投递通道，非事实来源）。

    实现负责把事件消息信封发送到工作队列；Worker 幂等消费（SPEC.md 第 11.3 节
    “Outbox 允许重复投递”）。投递失败必须抛 OutboxDeliveryError，使调度编排回滚
    事务、保留 PENDING 由补偿重投（D-011）。领域/应用层不导入 Celery/Redis SDK，
    仅依赖本端口（ADR-005、PLAN.md 第 3.4 节 EventPublisher 端口）。
    """

    def deliver(self, claim: OutboxEventClaim) -> None:
        """投递一条已领取事件；失败抛 OutboxDeliveryError。"""
        ...
