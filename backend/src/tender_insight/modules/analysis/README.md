# 分析运行模块（analysis）

> 异步分析运行的编排与任务事实来源（阶段 D）。PostgreSQL 是业务状态唯一事实来源，
> Celery/Redis 仅作投递通道，不承载权威状态（ADR-004/005）。

## 职责

- 管理 AnalysisRun 生命周期（DRAFT→QUEUED→…→READY→PUBLISHED→OUTDATED）与独立完整性字段；
- 记录不可变输入指纹与输入版本集合（运行 ↔ DocumentVersion 关系）；
- 编排 AnalysisTask / TaskAttempt 与 Outbox 事件投递、重试、心跳、取消与恢复；
- 提供权威进度快照（SSE 仅通知，查询快照为权威）。

## 入口

- 应用用例：发起运行、取消、重试、进度查询（阶段 D 后续任务）；
- ORM Model：`AnalysisRunModel`、`AnalysisRunInputModel`（infrastructure）；
- 状态机：`AnalysisRunStatus`、`AnalysisRunCompleteness`、`AnalysisTaskStatus`（shared/states.py）。

## 状态

- 运行状态：`AnalysisRunStatus`（SPEC.md 第 5.3 节）；
- 完整性：`AnalysisRunCompleteness`（COMPLETE/INCOMPLETE），独立于状态；
- 任务状态：`AnalysisTaskStatus`（SPEC.md 第 5.4 节）；
- 状态与完整性禁止用单字段混合（ADR-011）。

## 依赖

- 上游模块：document（输入版本集合与指纹）、project（运行归属 project_id）；
- 下游模块：risk、review、report（消费分析产物）；
- 端口：任务投递、进度投影、时钟（阶段 D 逐步定义）；
- 共享内核：states、state_transitions、identifiers、business_time、errors、pagination。

## 禁区

- domain 不导入 FastAPI/SQLAlchemy/Celery/Redis/供应商 SDK（A-006 守护）；
- 不得把业务状态放入 Redis/Celery/内存；Celery Result Backend 不参与完整性判断；
- 不得跨模块直接读写 ORM Model；Worker 从数据库校验 project_id/run_id/task_id 关联；
- 不引入身份/权限/租户字段或兼容分支。
