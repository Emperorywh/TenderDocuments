"""Celery 应用工厂（D-012）。

创建 Celery 应用并应用 D-012 队列路由：声明全部队列（含默认队列），注册按 task_type
路由的 callable router。broker URL（Redis）由外部注入，便于测试与部署分别提供；
Celery/Redis 是投递通道，非业务事实来源（ADR-004、ADR-005）。

Celery 不承载业务状态机（ADR-005）：Task 只加载上下文并调用应用用例，结果以短事务
写回 PostgreSQL（后续 D 任务实现具体 Task 主体）。
"""

from __future__ import annotations

from celery import Celery
from kombu import Queue

from tender_insight.workers.queues import (
    ALL_QUEUE_NAMES,
    DEFAULT_QUEUE,
    route_for_task,
)


def create_celery_app(
    broker_url: str,
    *,
    backend_url: str | None = None,
    app_name: str = "tender-insight",
) -> Celery:
    """创建配置好队列与路由的 Celery 应用。

    broker_url 为 Redis 连接串（投递通道）；backend_url 可选（Celery Result Backend，
    不参与业务完整性判断，ADR-005）。声明全部队列并注册 task_type 路由。
    """
    app = Celery(app_name, broker=broker_url, backend=backend_url)
    # 声明全部队列：默认队列 + 6 个 task_type 队列（D-012）。
    app.conf.task_queues = tuple(Queue(name) for name in ALL_QUEUE_NAMES)
    app.conf.task_default_queue = DEFAULT_QUEUE
    # 注册 callable router：按消息中的 task_type 路由到唯一队列。
    app.conf.task_routes = (route_for_task,)
    return app
