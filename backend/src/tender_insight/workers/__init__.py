"""worker 进程层（Celery）。

Celery Task 只加载任务上下文并调用应用用例，不承载业务状态机（ADR-005）；业务状态
唯一事实来源为 PostgreSQL。本包定义队列路由（D-012）与 Celery 应用工厂；具体 Task
主体随各业务阶段（解析、抽取、风险、报告）补充。
"""

from __future__ import annotations
