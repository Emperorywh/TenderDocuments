"""Celery 投递适配器（D-010）。

将已领取的 outbox 事件经 Celery `send_task` 投递到工作队列。Celery/Redis 是投递
通道，不是业务事实来源（ADR-004、ADR-005）；Worker 幂等消费（SPEC.md 第 11.3 节）。

为使领域/应用层不依赖 Celery SDK，Celery 应用实例由外部（bootstrap，D-012）注入；
本适配器运行期以鸭子类型调用 `send_task`，仅类型注解在 TYPE_CHECKING 下引用 Celery，
便于测试以伪对象替换真实 Celery（本机无 Celery worker 时仍可验证投递与确认逻辑）。

投递任务名（worker 侧统一入口）由配置注入，不在领域层硬编码。事件 payload 作为
消息体发送；event_id 作为幂等键随消息传递，供 Worker 去重。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tender_insight.modules.outbox.application import (
    OutboxDeliveryError,
    OutboxEventClaim,
)

if TYPE_CHECKING:  # 仅类型注解用，避免运行期 Celery 耦合。
    from celery import Celery


class CeleryOutboxBroker:
    """经 Celery send_task 投递 outbox 事件的适配器。

    celery_app 与 task_name 由外部注入：celery_app 为 bootstrap 创建的 Celery 实例
    （测试可传入伪对象，仅需实现 send_task）；task_name 为 worker 侧统一消费入口。
    结构性满足 outbox OutboxBroker 端口（由契约测试验证，不显式继承以保持适配器
    与端口解耦）。
    """

    def __init__(self, celery_app: Celery, task_name: str) -> None:
        self._celery_app = celery_app
        self._task_name = task_name

    def deliver(self, claim: OutboxEventClaim) -> None:
        """投递一条事件到 Celery；任一底层异常归一为 OutboxDeliveryError。

        归一化异常使调度编排只需识别 OutboxDeliveryError 即可回滚与补偿（D-011），
        不必逐个捕获 Celery/Redis 的多种异常类型。
        """
        try:
            self._celery_app.send_task(
                self._task_name,
                kwargs={
                    "event_id": claim.event_id,
                    "event_type": claim.event_type,
                    "aggregate_type": claim.aggregate_type,
                    "aggregate_id": claim.aggregate_id,
                    "payload": claim.payload,
                },
            )
        except OutboxDeliveryError:
            raise
        except Exception as exc:  # noqa: BLE001 - 统一归一为稳定投递失败错误。
            raise OutboxDeliveryError(
                f"投递事件 {claim.event_id} 到 Celery 任务 {self._task_name} 失败: {exc}"
            ) from exc
