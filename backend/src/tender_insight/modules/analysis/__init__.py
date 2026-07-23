"""analysis 模块：异步分析运行与原子任务的编排与事实来源（阶段 D 起）。

按 SPEC.md 第 5.3、5.4 节与 ADR-004/005，AnalysisRun 与 AnalysisTask 的业务状态
唯一事实来源是 PostgreSQL；Celery/Redis 仅作投递通道，不承载权威状态。文件接入
状态（DocumentVersion）与分析运行状态是两个独立状态机，禁止用单字段混合。
"""
