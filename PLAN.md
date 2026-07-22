# 四川建筑施工招标文件智能解读与投标风险提示系统 MVP 技术实施计划

> 计划版本：V1.0  
> 日期：2026-07-22  
> 输入基线：SPEC.md  
> 当前阶段：仅规划，不开始编码

## 1. 实施目标

在单一代码仓库中建设 React 桌面端、FastAPI 模块化单体 API、Celery Worker、PostgreSQL、Redis、S3 兼容对象存储和 PaddleOCR 文档处理链，最终部署到单台 Linux 服务器。

首版采用单实例、单工作区模式，不建设用户、组织、登录会话、角色权限、租户字段或 RLS。所有业务入口能力一致，生产访问边界由受控内网、VPN 或等价网络措施承担。

计划以完整纵向业务闭环为目标：

    项目与文件
    → 异步解析
    → 结构化抽取
    → 风险分析
    → 人工复核
    → 不可变报告
    → PDF 导出

不建设旧系统兼容层，不保留 legacy、fallback、deprecated 或灰度分支。

## 2. 总体技术基线

### 2.1 前端

- React 19；
- TypeScript；
- Vite；
- React Router；
- TanStack Query；
- React Hook Form；
- Zod；
- Ant Design；
- PDF.js；
- OpenAPI 生成客户端；
- Vitest 与 Testing Library。

### 2.2 后端

- Python 3.12；
- FastAPI；
- Pydantic 2；
- SQLAlchemy 2；
- Alembic；
- psycopg 3；
- Celery 5；
- redis-py；
- HTTPX；
- uv；
- pytest；
- Ruff；
- Pyright。

### 2.3 文档与 AI

- LibreOffice Headless；
- PyMuPDF；
- pdfplumber；
- PaddleOCR PP-StructureV3；
- Pillow；
- OpenCV；
- DeepSeek OpenAI-compatible API；
- Pydantic JSON Schema；
- Jinja2；
- WeasyPrint。

### 2.4 数据与运行环境

- PostgreSQL 17；
- Redis 7；
- MinIO 或其他 S3 兼容存储；
- Docker 与 Docker Compose；
- Nginx；
- OpenTelemetry；
- Prometheus 与 Grafana；
- structlog。

具体补丁版本在项目初始化时锁定。DeepSeek 模型 ID 由环境变量配置，不进入领域代码。

## 3. 架构边界

### 3.1 仓库结构

    tender-insight/
    ├── frontend/
    │   ├── src/
    │   │   ├── app/
    │   │   ├── features/
    │   │   ├── entities/
    │   │   ├── shared/
    │   │   └── generated-api/
    │   └── tests/
    ├── backend/
    │   ├── src/
    │   │   ├── modules/
    │   │   │   ├── project/
    │   │   │   ├── document/
    │   │   │   ├── knowledge/
    │   │   │   ├── analysis/
    │   │   │   ├── risk/
    │   │   │   ├── review/
    │   │   │   ├── report/
    │   │   │   └── operation_log/
    │   │   ├── model_gateway/
    │   │   ├── rule_packs/
    │   │   │   └── sichuan_construction/
    │   │   ├── workers/
    │   │   ├── shared/
    │   │   ├── bootstrap/
    │   │   └── main.py
    │   ├── migrations/
    │   └── tests/
    ├── evaluation/
    ├── infra/
    └── docs/

### 3.2 模块内部结构

每个领域模块采用同一分层：

    module/
    ├── domain/
    ├── application/
    ├── infrastructure/
    └── api/

约束：

- domain 不依赖 Web、ORM、队列和供应商 SDK；
- application 负责编排用例、事务、幂等和跨模块协作；
- infrastructure 实现仓储和外部端口；
- api 只做协议转换、请求上下文和用例调用；
- Celery Task 只加载任务上下文并调用应用用例；
- 查询展示可使用只读投影，但不得通过投影写回领域表；
- shared 只接收具有稳定语义和两个以上真实消费者的代码；
- 不创建全局巨型 services.py、models.py 或 utils.py。

### 3.3 跨模块依赖

允许的主要方向：

    project ← document ← knowledge
                analysis
                   ↓
           risk → review → report

    operation_log 通过应用端口接收关键操作事件，不反向控制业务状态

实际协作通过应用服务、端口、领域事件和事务 Outbox 完成。任何模块不得导入另一模块的 ORM Model 并修改其数据。

### 3.4 关键端口

首版明确以下替换边界：

- ObjectStorage；
- FileSecurityScanner；
- DocumentConverter；
- NativeTextExtractor；
- PageRenderer；
- OcrEngine；
- LayoutAnalyzer；
- ClauseSegmenter；
- ModelGateway；
- RulePack；
- ReportRenderer；
- EventPublisher；
- Clock。

## 4. 关键设计决策

实施前建立并维护以下 ADR：

- ADR-001：后端统一采用 Python；
- ADR-002：采用模块化单体；
- ADR-003：API 与 Worker 同库不同进程；
- ADR-004：PostgreSQL 是业务状态事实来源；
- ADR-005：Celery 不承担业务状态机；
- ADR-006：原文件不可变且 DOCX 生成标准 PDF；
- ADR-007：正式结论必须有证据；
- ADR-008：解析器、模型、提示词、Schema 和规则版本化；
- ADR-009：四川规则独立扩展包；
- ADR-010：报告采用不可变快照；
- ADR-011：文件接入、分析运行、任务和完整性分离建模；
- ADR-012：DeepSeek 通过 ModelGateway 适配；
- ADR-013：首版单 Linux Docker Compose 部署。
- ADR-014：首版采用无应用鉴权的单实例单工作区模式。

## 5. 数据与状态实施策略

### 5.1 数据库按模块归属

每张表具有唯一业务模块所有者。跨模块只保存稳定 ID，不通过数据库级共享实体制造隐式所有权。

建议迁移批次：

1. project：项目和删除生命周期；
2. operation_log 与 outbox：关键操作记录、事务事件；
3. document：文件、版本、关系、上传会话、页面和页面块；
4. analysis：运行、任务、尝试和输入版本集合；
5. knowledge：章节、条款、候选事实、事实、候选要求和要求；
6. risk 与 review：候选风险、正式风险、证据和复核记录；
7. report：报告快照、导出产物；
8. model_gateway：模型调用元数据和受限响应引用。

### 5.2 事务边界

- 业务命令在单一应用用例内开启事务；
- 同一模块聚合修改和 OutboxEvent 在同一事务提交；
- 文件二进制先进入临时对象，校验通过后再完成业务接入；
- Worker 先计算候选产物，再以短事务提交；
- 外部 API 调用不得持有数据库事务；
- 报告快照创建与发布状态变更在同一事务完成，PDF 渲染作为后续幂等任务。

### 5.3 单工作区与项目归属

- 首版数据库不建立用户、组织、成员、角色、会话和令牌表；
- 业务表不包含 organization_id、user_id、created_by 或 reviewed_by；
- 不启用基于租户的 PostgreSQL RLS；
- 项目内实体显式包含或可通过稳定外键推导 project_id；
- Repository 的项目内查询必须显式接收 project_id，不提供无范围的业务数据扫描接口；
- Worker 从数据库校验 project_id、analysis_run_id 和 analysis_task_id 的关联，消息只用于定位，不作为归属事实来源；
- 单工作区不是多租户隔离方案，生产访问依赖受控内网、VPN 或等价网络边界。

### 5.4 幂等

数据库唯一约束至少覆盖：

- 文件哈希在项目和逻辑版本范围内的重复规则；
- 分析运行输入指纹；
- AnalysisTask 幂等键；
- 正式候选晋升结果；
- ReviewAction 客户端幂等键；
- ReportSnapshot 输入指纹；
- OutboxEvent 业务事件 ID。

## 6. 分阶段实施

## 阶段 0：领域基线和项目骨架

### 目标

在写业务功能前固定模块边界、状态、错误码和工程约束。

### 工作

- 建立单仓目录；
- 锁定 Python、Node 和系统依赖版本；
- 建立后端、前端和基础设施最小启动入口；
- 建立 ADR、模块 README 和依赖规则；
- 定义 UUID、时间、金额、分页、错误和请求追踪等共享语义；
- 定义文件、分析、任务、复核和报告状态机；
- 建立 Ruff、Pyright、pytest、TypeScript 和前端测试配置；
- 建立 Docker Compose 开发依赖。

### 完成条件

- API、空 Worker 和前端可以分别启动；
- 模块依赖规则有自动检查；
- 状态转换表和领域测试存在；
- 从空库可以执行第一版迁移。

## 阶段 1：项目生命周期和关键操作记录

### 目标

完成单工作区项目入口、项目生命周期和不依赖用户身份的关键操作留痕，为后续业务建立稳定的顶层数据边界。

### 工作

- Project 聚合；
- 项目创建、编辑和列表投影；
- 项目归档、恢复和待删除；
- Project 作为顶层数据归属边界；
- OperationLog 只追加写入；
- 请求 ID、动作、资源和结果记录；
- 前端直接进入项目列表，不建立登录和权限路由；
- 项目列表和项目表单。

### 完成条件

- 空库迁移中不存在用户、组织、角色、会话或令牌表；
- 项目内数据都能通过稳定关系回到 project_id；
- 关键操作记录不伪造操作者身份且不承载业务状态；
- 打开应用可直接创建第一个项目。

## 阶段 2：对象存储、文件和版本

### 目标

可靠接入不可变文件，为解析链提供确定输入。

### 工作

- ObjectStorage 端口及 MinIO 适配器；
- 临时上传会话和预签名地址；
- 文件大小、MIME、魔数、空文件和压缩异常校验；
- SHA-256；
- quarantine 和安全检查状态；
- Document、DocumentVersion、DocumentRelation；
- 文件类型、生效顺序和替代关系确认；
- 单项目 500 页限制；
- 原始文件私有访问；
- 文件管理页面。

### 完成条件

- 三种输入格式可安全接入；
- 重复文件不触发重复分析；
- 历史版本不可覆盖；
- 原始对象默认私有且只能通过短期授权地址访问；
- 文件版本集合可以形成稳定输入指纹。

## 阶段 3：异步任务和状态事实来源

### 目标

建立可恢复、可重试、可取消和可观测的计算底座。

### 工作

- AnalysisRun、AnalysisTask、TaskAttempt；
- OutboxEvent；
- Scheduler 投递和补偿；
- Celery 队列路由；
- Worker 心跳；
- 指数退避和错误分类；
- 幂等领取和原子结果提交；
- 取消协作；
- 卡死任务扫描；
- SSE 和进度快照；
- 分析进度页面。

### 完成条件

- 数据库提交后任务不会因瞬时投递失败永久丢失；
- 重复消息不产生重复业务结果；
- Worker 崩溃后任务可恢复；
- Celery Result Backend 不参与完整性判断；
- 前端只展示数据库计算出的真实进度。

## 阶段 4：文档标准化、解析和证据坐标

### 目标

把 PDF、扫描 PDF 和 DOCX 转为可复现、逐页、可定位的知识输入。

### 工作

- 固定 LibreOffice 和字体环境；
- DOCX 转标准 PDF；
- PyMuPDF 原生文本、坐标和页面渲染；
- 页面文本质量算法；
- PaddleOCR 与图像预处理；
- 页面旋转和坐标归一化；
- Page、PageBlock、Section、Clause；
- 目录和章节识别；
- 失败页和完整性；
- PDF.js 文档阅读器基础；
- 证据高亮回归样本。

### 完成条件

- 三种代表性文档可以逐页查看；
- OCR 仅在页面质量不足时触发；
- 每页有确定状态和版本元数据；
- 任一证据能回查文件、页码、原文和坐标；
- 失败页不会静默跳过。

## 阶段 5：知识抽取和 DeepSeek 网关

### 目标

建立候选与正式结果分离的结构化抽取链。

### 工作

- ProjectFactCandidate、ProjectFact；
- RequirementCandidate、Requirement；
- 每类任务独立 Pydantic Schema；
- PromptRegistry 和版本；
- ModelGateway 端口；
- DeepSeek OpenAI-compatible 适配器；
- 经济模型和强模型配置；
- JSON 输出解析、空响应和截断处理；
- 条款 ID 和原文一致性验证；
- 模型调用 Token、耗时和费用；
- 全量条款扫描；
- 候选晋升应用用例。

### 完成条件

- 模型不能直接写正式领域表；
- 模型返回的伪造页码和未知条款 ID 被拒绝；
- 外部调用失败有明确错误码和重试记录；
- 正式事实和要求都有证据；
- DeepSeek 模型切换无需修改领域模块。

## 阶段 6：规则、风险和独立验证

### 目标

完成 MVP 全部 P0 分析能力。

### 工作

- 四川规则包 Manifest；
- 项目事实归一化和版本优先级；
- 资格要求；
- 显式和隐式否决风险；
- 评分项和 Decimal 总分闭合；
- 关键时间和延期失效；
- 材料清单；
- 技术标约束；
- 报价与限价；
- 合同风险提示；
- 文件冲突；
- 完整性规则；
- CRITICAL/HIGH 独立验证；
- RiskCandidate、RiskFinding 和 SourceCitation。

### 完成条件

- 所有 P0 分类均能生成结构化结果；
- 无证据候选不能晋升；
- 冲突至少有两个证据；
- 评分不闭合和失败页正确影响完整性；
- 无企业资料时资格状态不会显示已满足。

## 阶段 7：人工复核、报告和 PDF

### 目标

形成可审计的人工闭环和不可变交付物。

### 工作

- ReviewAction；
- 乐观并发控制；
- 单条确认、修订和驳回；
- 批量确认和批量驳回；
- 发布条件策略；
- ReportSnapshot；
- Jinja2 HTML 模板；
- WeasyPrint PDF；
- 报告哈希和渲染器版本；
- 新文件导致报告过期；
- 不包含用户身份的关键操作记录。

### 完成条件

- 系统结论和人工结论并存；
- 批量复核逐项返回结果；
- 不完整或高风险未复核的报告不能发布；
- 同一输入重复发布保持幂等；
- 历史报告不会因重分析改变。

## 阶段 8：桌面端完整体验

### 目标

完成简约、桌面优先的全部业务页面。

### 工作

- 应用壳和业务路由；
- 项目、文件和进度页面；
- 报告总览；
- 资格、否决、评分和时间页面；
- 材料、技术、报价和合同报告分区；
- 风险筛选和批量选择；
- 证据抽屉；
- PDF.js 虚拟化和高亮；
- 报告发布与 PDF 下载；
- 失败、空状态和加载提示；
- URL 保存筛选、分页和阅读位置。

### 完成条件

- 服务端状态只由 TanStack Query 管理；
- 全局 Store 不复制分析、风险或文件状态；
- 证据抽屉关闭后上下文保持；
- 高风险不只依赖颜色；
- UI 不展示假进度或隐藏失败。

## 阶段 9：Linux 部署和人工验收

### 目标

在目标 Linux 环境交付可备份、可恢复、可回滚的 MVP。

### 工作

- API、通用 Worker、OCR Worker、Scheduler 和前端镜像；
- PostgreSQL、Redis、MinIO 和 Nginx Compose 配置；
- TLS、Secret 和防火墙；
- Alembic 独立迁移流程；
- 数据卷和备份；
- 日志、指标和 Trace；
- 发布、停止接单、任务排空和回滚脚本；
- 人工验收数据准备；
- 按 SPEC.md 第 15 章逐项验收。

### 完成条件

- 空 Linux 主机可按文档完成部署；
- 重启不丢失原始文件和业务状态；
- 数据库和对象存储完成一次恢复演练；
- 用户完成全部人工验收项并记录结果。

## 7. 前后端协作策略

- 后端先定义 OpenAPI Schema 和稳定错误码；
- 前端客户端只能从 OpenAPI 生成；
- 命令接口返回业务结果或异步 ID，不返回虚假完成；
- SSE 只是通知机制，查询快照仍是权威状态；
- 前端每个 feature 对应后端用例，不直接映射数据库表；
- UI 开发可在相应后端阶段完成契约后并行进行；
- Schema 变更必须同时更新契约测试和生成客户端。

## 8. DeepSeek 实施细节

### 8.1 配置

至少提供：

- DEEPSEEK_BASE_URL；
- DEEPSEEK_API_KEY；
- DEEPSEEK_FAST_MODEL；
- DEEPSEEK_STRONG_MODEL；
- DEEPSEEK_TIMEOUT_SECONDS；
- DEEPSEEK_MAX_CONCURRENCY；
- DEEPSEEK_PROJECT_BUDGET；
- DEEPSEEK_JSON_MODE。

不得在代码中使用即将失效或特定时期的模型别名作为业务逻辑。

### 8.2 请求生命周期

    原子条款输入
    → Prompt 与 Schema 版本冻结
    → 预算和并发检查
    → DeepSeek JSON 请求
    → JSON 解析
    → Pydantic 校验
    → 条款与原文校验
    → 领域规则校验
    → 候选结果
    → 独立验证
    → 正式结果

### 8.3 失败策略

- 网络、超时、限流：有限自动重试；
- 空内容、截断、JSON 错误：记录原始响应引用后有限重试；
- Schema 或证据错误：不晋升正式结果；
- 超出预算：任务明确失败并要求人工处理；
- 不静默切换模型或供应商；
- 重试和人工重跑均创建新的 TaskAttempt。

## 9. 测试和验收实施

### 9.1 开发验证

测试不作为自动发布门禁，但每个任务必须有与风险相称的验证：

- 纯领域规则使用单元测试；
- 数据库约束、项目归属关系和事务使用 PostgreSQL 集成测试；
- Redis、MinIO 和任务流使用真实依赖测试；
- 文档坐标使用固定回归文件；
- DeepSeek 使用录制响应和受控真实调用；
- 前端使用组件测试验证状态和交互；
- 不由 Codex 自动启动浏览器测试。

### 9.2 人工验收

- 以 SPEC.md 第 15 章为唯一首版功能验收清单；
- 每个验收项记录通过、失败、证据和备注；
- 至少准备原生 PDF、扫描 PDF 和 DOCX 各一个；
- 至少包含一个补遗或延期场景；
- 至少包含一个失败页、评分不闭合或文件冲突场景；
- AI 指标仅记录，不阻止人工确认上线。

## 10. 部署步骤

1. 准备 Linux、Docker、Compose、域名和 TLS；
2. 创建专用运行用户、数据目录和备份目录；
3. 注入生产 Secret 和强类型配置；
4. 拉取带版本号的不可变镜像；
5. 启动 PostgreSQL、Redis 和 MinIO；
6. 执行基础设施健康检查；
7. 备份当前版本数据；
8. 独立执行 Alembic 迁移；
9. 启动 API、Worker、OCR Worker 和 Scheduler；
10. 启动前端和 Nginx；
11. 检查 API、队列、对象存储、DeepSeek 和 OCR；
12. 验证业务入口只能从受控内网、VPN 或等价网络边界访问；
13. 开放新分析运行；
14. 执行人工冒烟和功能验收。

## 11. 回滚步骤

### 11.1 无破坏性迁移

1. 停止接收新分析；
2. 停止 Scheduler 投递；
3. 等待短任务结束或进入安全取消；
4. 切换到上一版本镜像；
5. 启动服务；
6. Scheduler 从 PostgreSQL 事实状态恢复任务；
7. 完成冒烟后重新开放分析。

### 11.2 破坏性迁移

1. 保持服务停止；
2. 验证发布前 PostgreSQL 和对象存储恢复点；
3. 将数据库和对象存储恢复到同一时间点；
4. 部署与该 Schema 匹配的上一版本镜像；
5. 清理不可信的 Redis 临时状态；
6. 从数据库任务状态重新投递；
7. 核对报告快照、文件哈希和任务完整性；
8. 人工批准后恢复访问。

## 12. 技术风险和控制

| 风险 | 控制 |
|---|---|
| 500 页项目导致内存和任务积压 | 逐页、逐章节任务，独立队列、限流和资源指标 |
| PaddleOCR CPU 耗时过长 | OCR 独立 Worker，页面质量门控，可配置并发 |
| DOCX 页码不稳定 | 固定 LibreOffice、字体和标准化 PDF |
| DeepSeek JSON 为空或截断 | 完成原因校验、Schema 校验、有限重试和失败可见 |
| 模型名称升级 | 模型 ID 环境变量配置，调用版本入库 |
| 模型产生无证据结论 | clause_id 回查、原文哈希、独立验证和晋升流程 |
| Celery 重复执行 | 幂等键、唯一约束和短事务提交 |
| Redis 丢失消息 | PostgreSQL Outbox 和 Scheduler 补偿 |
| 无应用鉴权导致入口暴露 | 生产仅允许受控内网、VPN 或等价网络边界访问，内部端口不公开，对象使用短期授权 |
| PDF 高亮偏移 | 归一化坐标、旋转元数据和固定回归文件 |
| 报告字体缺失 | 固定中文字体镜像和 PDF 视觉检查 |
| 单机故障 | 定期备份、恢复演练和可重建容器 |

## 13. 架构一致性检查

每个阶段完成后检查：

- 是否新增跨模块 ORM 写入；
- 是否把业务状态放入内存、Redis 或 Celery；
- 是否出现无法解释的共享工具；
- 是否出现巨型路由、Task、Service 或组件；
- 是否复制 Schema、规则或错误处理；
- 是否出现隐式模型选择、状态转换或项目归属；
- 是否有新魔法常量；
- 是否能从 ID、版本和证据推导结果；
- 是否保持候选、正式结果和人工结果分离；
- 是否降低了 AI 和开发者理解代码的能力。

发现边界不合理时先重构边界，再继续增加功能。

## 14. 计划完成定义

实施计划完成不等同于代码写完。必须同时满足：

- SPEC.md 的范围全部交付；
- TASKS.md 中所有首版任务独立验证完成；
- 模块、状态、数据和接口边界符合本计划；
- Linux 部署、备份和恢复流程经过验证；
- 用户依据人工功能清单完成验收；
- 不存在用临时 patch、隐式 fallback 或跳过失败掩盖未完成项的情况。
