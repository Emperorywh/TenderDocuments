"""outbox 模块：事务性事件投递（阶段 D）。

实现事务 Outbox 模式（SPEC.md 第 5.2、11.2、11.3 节，ADR-004）：业务变更与对应
事件在同一数据库事务写入 outbox 表，由 Scheduler 异步领取并投递到 Celery/Redis。
Outbox 允许重复投递，Worker 必须幂等消费；PostgreSQL 是唯一事实来源。
"""
