# 架构决策记录（ADR）

本目录记录四川建筑施工招标文件智能解读与投标风险提示系统的架构决策，编号与
PLAN.md 第 4 节一致。每份 ADR 至少包含：

- 状态（Proposed / Accepted / Superseded）；
- 背景（Context）：决策所应对的问题与约束；
- 决策（Decision）：所选方案；
- 后果（Consequences）：带来的收益与代价；
- 重评条件（Reconsider when）：何种变化应触发重新评估该决策。

## 索引

| 编号 | 标题 |
|---|---|
| [ADR-001](0001-python-backend.md) | 后端统一采用 Python |
| [ADR-002](0002-modular-monolith.md) | 采用模块化单体 |
| [ADR-003](0003-shared-codebase-api-worker.md) | API 与 Worker 同库不同进程 |
| [ADR-004](0004-postgresql-source-of-truth.md) | PostgreSQL 是业务状态事实来源 |
| [ADR-005](0005-celery-not-state-machine.md) | Celery 不承担业务状态机 |
| [ADR-006](0006-immutable-files-and-canonical-pdf.md) | 原文件不可变且 DOCX 生成标准 PDF |
| [ADR-007](0007-evidence-required.md) | 正式结论必须有证据 |
| [ADR-008](0008-versioned-pipeline.md) | 解析器、模型、提示词、Schema 和规则版本化 |
| [ADR-009](0009-sichuan-rule-pack.md) | 四川规则独立扩展包 |
| [ADR-010](0010-immutable-report-snapshot.md) | 报告采用不可变快照 |
| [ADR-011](0011-separated-state-modeling.md) | 文件接入、分析运行、任务和完整性分离建模 |
| [ADR-012](0012-model-gateway-for-deepseek.md) | DeepSeek 通过 ModelGateway 适配 |
| [ADR-013](0013-single-linux-compose-deploy.md) | 首版单 Linux Docker Compose 部署 |
| [ADR-014](0014-single-workspace-no-auth.md) | 首版采用无应用鉴权的单实例单工作区模式 |
