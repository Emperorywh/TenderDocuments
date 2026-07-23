# 项目进度

## 1. 当前总体状态

* 当前阶段：阶段 D 进行中；`C-001`～`C-034` 全部完成，`D-001`～`D-007` 已完成，下一任务 `D-008`。
* 整体完成度：`83 / 326` 个原子开发任务完成（约 `25.5%`）。
* 当前分支：`main`，HEAD 为 `D-007` 提交（待创建）。
* 最后更新时间：2026-07-22（Asia/Shanghai）。
* 当前是否存在阻塞：是（环境约束，详见第 5 节）。`A-002` 要求 uv 锁文件，而当前环境未安装 `uv`；后续阶段 B/C/D/E/F 还需要 Docker、PostgreSQL、Redis、MinIO、LibreOffice、PaddleOCR、DeepSeek、WeasyPrint、Linux 等。在受限环境下优先构建可在当前环境验证的代码与配置，并在本文件如实记录哪些验证已执行、哪些因外部依赖未就绪而待执行。

已确认的仓库状态：

* 在 `A-001` 之前，仓库只有 6 份 Markdown 文档；`A-001` 新增 `frontend/`、`backend/`、`evaluation/`、`infra/`、`docs/` 五个顶层目录，各含一份说明职责边界的 `README.md`。
* `TASKS.md` 中 `A-001` 已勾选 `[x]`，其余 325 个任务仍为 `[ ]`。

## 2. 当前任务

* Task 编号：`C-033`、`C-034`、`C-030`
* Task 名称：原始文件访问 API、上传完成 API、文件操作记录接入
* 当前状态：待开始。
* 前置依赖：`C-032` 及各前置（已完成）。
* 当前目标：原始文件短期下载地址、上传完成确认端点、文件操作记录接入。
* 阻塞风险：C-033/C-034 依赖对象存储适配器；C-030 复用 B-017 记录模式。

需要持续遵守的约束：

* 全新系统，不兼容旧代码或旧数据，不引入 legacy、灰度、fallback、deprecated 或兼容分支。
* 首版为单实例、单工作区、无应用鉴权；禁止预埋用户、组织、角色、Token、RBAC、多租户字段或 RLS。
* 采用模块化单体和显式分层；领域层不得依赖 FastAPI、Celery、SQLAlchemy 或模型 SDK。
* PostgreSQL 是业务状态唯一事实来源；Redis、Celery 和前端缓存不承载权威业务状态。
* 新增或修改代码必须使用必要的多行简体中文注释；不得主动格式化既有代码；不得自动启动浏览器测试。

## 3. 已完成任务

### D-007 建立 OutboxEvent 迁移

* 实现摘要：新增 outbox 模块（domain/infrastructure + README）与 OutboxEventModel（event_id 全表唯一、event_type、aggregate_type/aggregate_id、payload JSON 消息信封、delivery_status、attempts、last_attempt_at）与迁移 0011，注册到 env.py。
* 验证结果（2026-07-23）：5 项测试通过——表结构且无身份字段、event_id 唯一约束存在、相同业务事件 ID 被拒(IntegrityError)、不同事件 ID 可并存、payload JSON 可完整回读；全量 380 项通过；ruff、pyright 0 错误。

### D-006 实现 AnalysisTask 状态机

* 实现摘要：新增 analysis domain `analysis_task.py`（AnalysisTask 聚合：create 工厂构造 PENDING、dispatch/start/succeed/schedule_retry/fail/cancel 状态转换方法经 validate_transition 集中校验，重试路径 RETRY_SCHEDULED→DISPATCHED、DISPATCHED/RUNNING 可失败、各活动状态可取消）。
* 验证结果（2026-07-23）：15 项领域测试通过——create 为 PENDING、主路径至 SUCCEEDED、重试路径、RETRY_SCHEDULED 可直接失败、DISPATCHED/RUNNING 可失败、各活动状态可取消、PENDING 不可跳 RUNNING、RUNNING 不可回退、SUCCEEDED/FAILED/CANCELLED 终态、SUCCEEDED/RETRY_SCHEDULED 只能从特定状态、空类型/空幂等键被拒；全量 375 项通过；ruff、pyright 0 错误。

### D-005 建立 TaskAttempt 迁移

* 实现摘要：新增 TaskAttemptModel（关联 analysis_task_id、attempt_number 任务内唯一自增、status 执行结果、started_at/finished_at、error_code）与迁移 0010，注册到 env.py。
* 验证结果（2026-07-23）：5 项测试通过——表结构且无身份字段、重试新增记录且旧失败尝试保留(attempt_number 自增)、同任务内 attempt_number 唯一、尝试必须关联任务(外键)、不同任务可各自从 1 编号；全量 360 项通过；ruff、pyright 0 错误。

### D-004 建立 AnalysisTask 迁移

* 实现摘要：新增 AnalysisTaskModel（analysis_run_id 与 project_id 双外键、task_type、status、idempotency_key 运行内唯一约束）与迁移 0009，注册到 env.py。
* 验证结果（2026-07-23）：6 项测试通过——表结构且无身份字段、任务必须关联运行(analysis_run_id FK)、必须关联项目(project_id FK)、可持久化回读运行与项目、同运行内幂等键唯一(防重复结果)、不同运行可复用幂等键；全量 355 项通过；ruff、pyright 0 错误。

### D-003 实现活动运行唯一规则

* 实现摘要：领域层定义 ACTIVE_RUN_STATUSES / TERMINAL_RUN_STATUSES 与 is_active_run_status（活动运行唯一权威定义：PUBLISHED/OUTDATED/CANCELLED/FAILED 非活动，允许失败重试与同输入重分析）；迁移 0008 为 analysis_runs 增加 partial unique index（project_id+input_fingerprint WHERE status NOT IN 终态），WHERE 子句与领域终态集一致。
* 验证结果（2026-07-23）：6 项测试通过——活动/终态集划分全覆盖且不重叠、同项目同输入第二个活动运行被拒（IntegrityError）、CANCELLED 后可再建活动运行、多个终态可并存、PUBLISHED 不阻止重分析、不同项目/不同指纹可并存；全量 349 项通过；ruff、pyright 0 错误。

### D-002 实现 AnalysisRun 状态机

* 实现摘要：新增 analysis domain `analysis_run.py`（AnalysisRun 聚合：create 工厂构造 DRAFT、input_fingerprint/input_version_ids 创建后不可变、状态转换方法 queue/start_parsing/start_extracting/start_analyzing/start_verifying/require_review/mark_ready/publish/request_cancel/confirm_cancelled/mark_failed/mark_outdated 经 validate_transition 集中校验、completeness 独立字段 set_completeness 不耦合状态）。
* 验证结果（2026-07-23）：15 项领域测试通过——create 为 DRAFT、主路径至 PUBLISHED→OUTDATED、VERIFYING→REVIEW_REQUIRED→READY、DRAFT 不可跳 PARSING、DRAFT 不可跳 READY、PUBLISHED 只能从 READY、活动状态均可取消/失败、CANCEL_REQUESTED 只能到 CANCELLED、终态不可流转、PUBLISHED 只能到 OUTDATED、完整性独立于状态、空指纹/空输入集合被拒、输入版本元组不可变；全量 343 项通过；ruff、pyright 0 错误。

### D-001 建立 AnalysisRun 迁移

* 实现摘要：新增 analysis 模块骨架（domain/application/infrastructure/api 四层 + README）；infrastructure `models.py` 定义 AnalysisRunModel（id/project_id/status/completeness 独立于 status/input_fingerprint/started_at，无身份字段）与 AnalysisRunInputModel（运行↔DocumentVersion 输入集合关系，position 保留生效顺序，唯一约束防重复计入）；迁移 0007 建两表与索引并注册到 env.py。
* 验证结果（2026-07-23）：6 项迁移测试通过——analysis_runs 表结构且无身份字段、status 与 completeness 为两个独立列(completeness 可空)、analysis_run_inputs 表结构、project_id 外键引用 projects、运行保存不可变输入指纹(C-026 真实指纹)与有序输入集合、唯一约束拒绝同版本重复计入；全量 328 项通过；ruff、pyright 0 错误。

### C-030 接入文件关键操作记录

* 实现摘要：将操作记录接入文件用例，复用 B-017 record_command_outcome 模式——上传发起(document.upload.create)、上传完成(document.upload.complete)、类型确认(document.confirm_type)、日期确认(document.confirm_published_date)、关系变更(document.relation.create)、下载(document.download)、查看(document.view) 各注入 session_factory+open_recorder；complete_upload 因对象移动先于提交的语义改用内联录制（成功同事务、失败经 persist_operation_failure 独立事务）；新增 ListDocumentsUseCase 包装只读查看查询。recording 模块将 _persist_failure 提升为公开 persist_operation_failure 供 complete_upload 复用，保持单一权威实现。
* 验证结果（2026-07-23）：10 项集成测试通过——上传发起/上传完成各 1 条 success、上传完成校验失败 1 条 failure(FILE_TYPE_MISMATCH)、类型确认/日期确认/关系/下载/查看各 1 条 success、未知文件确认 1 条 failure(NOT_FOUND)、各动作名互异；全量 322 项通过；ruff、pyright 0 错误。阶段 C 全部完成。
* 阶段 C 总结：C-001～C-034 全部完成——ObjectStorage 端口与 MinIO 适配器、上传会话与预签名、文件真实性/完整性/压缩/SHA-256 校验、Document/Version/Relation 不可变模型与迁移、上传完成接入、重复文件策略、quarantine 安全闸门、业务类型/发布日期/生效顺序/替代关系确认、分析输入版本集合与指纹、部署限额与 500 页限制、文件列表/元数据/关系/原始文件访问/上传完成 API、文件关键操作记录。所有文件 API 无身份字段、对象默认私有经短期授权访问。

### C-033 发布原始文件访问 API

* 实现摘要：新增 document application `create_original_file_access_url.py`（CreateOriginalFileAccessUrlUseCase：载入版本→解析原始对象键→签发 presigned_get_url，返回 download_url/expires_at，不含对象键）与 GET /api/v1/documents/versions/{version_id}/original-url；TTL 取自配置 presigned_url_ttl_seconds。
* 验证结果（2026-07-23）：3 项契约测试通过——成功 200 且响应键集合仅 {download_url, expires_at, method}（无 object_key）、presigned_get_url 以配置 TTL 调用、未知版本 404 NOT_FOUND；全量 312 项通过；ruff、pyright 0 错误。

### C-034 发布上传完成 API

* 实现摘要：document API 新增 POST /api/v1/upload-sessions/{session_id}/complete → CompleteUploadUseCase（201 返回 document_id/version_id/version_number/sha256）；为压缩校验限额补充强类型配置 max_uncompressed_bytes/max_compression_ratio（避免魔法常量）。
* 验证结果（2026-07-23）：3 项契约测试通过——成功 201 创建版本且无身份字段、类型不符 400 FILE_TYPE_MISMATCH 且无业务残留（0 Document/Version）、未知会话 404 NOT_FOUND；全量 309 项通过；ruff、pyright 0 错误。

### C-032 发布文件关系 API

* 实现摘要：document API 新增 POST /api/v1/documents/relations → CreateDocumentRelationUseCase（循环替代/跨项目/自引用均返回 409 CONFLICT）。
* 验证结果（2026-07-23）：3 项契约测试通过——关系创建 201、循环替代 409 CONFLICT、跨项目 409；全量 306 项通过；ruff、pyright 0 错误。

### C-031 发布文件元数据确认 API

* 实现摘要：document API 新增 PATCH /documents/{id}/type（确认业务类型）与 PATCH /documents/versions/{version_id}/published-date（确认发布日期）；NaiveBusinessTimeError 改继承 DomainError 使 handler 统一映射为 400。
* 验证结果（2026-07-23）：4 项契约测试通过——类型确认 200、非法类型 422、带时区日期 200、无时区日期 400 NAIVE_BUSINESS_TIME；全量 303 项通过；ruff、pyright 0 错误。

### C-029 发布文件列表 API 契约

* 实现摘要：新增 document `application/list_documents.py`（DocumentListItem 投影：业务类型/确认状态/版本数/时间，DB 级分页 + 版本数子查询）与 GET /api/v1/projects/{project_id}/documents 端点。
* 验证结果（2026-07-23）：2 项契约测试通过——分页返回正确字段集合（含 confirmed/version_count）与页大小上限 422；全量 299 项通过；ruff、pyright 0 错误。

### C-028 实现 PDF 页数限制

* 实现摘要：新增 document domain `page_limit.assert_project_pages`（current+adding 超 max_pages 抛 FileLimitExceededError，第 max_pages 页允许、第 max_pages+1 页拒绝）；max_pages 来自配置 max_project_pages（业务硬限制默认 500）。同时修复 FileLimits.from_settings 用结构化 Protocol（_LimitSettings）满足 ruff/pyright。
* 验证结果（2026-07-23）：4 项测试通过——500 页允许、501 页拒绝、0 新增在内、大额新增拒绝；全量 297 项通过；ruff、pyright 0 错误。

### C-027 实现部署字节与文件数限制

* 实现摘要：新增 document domain `FileLimits`（from_settings 从强类型配置构造、assert_file_size/file_count/project_bytes）与 FileLimitExceededError（code FILE_LIMIT_EXCEEDED）；限额全部来自配置，领域无魔法常量。
* 验证结果（2026-07-23）：5 项测试通过——限额来自配置、修改配置改变限制、单文件大小/文件数/总字节分别校验；全量 293 项通过；ruff、pyright 0 错误。

### C-026 实现输入版本指纹

* 实现摘要：新增 document domain `input_fingerprint.compute_input_fingerprint`（以 (version_id, sha256) 成员，先按 version_id 排序再 SHA-256，顺序无关、内容敏感）。
* 验证结果（2026-07-23）：5 项测试通过——同集合重排指纹不变、内容变化指纹变化、成员变化指纹变化、空集稳定、不同集合不同指纹；ruff、pyright 0 错误。

### C-025 实现分析输入版本集合

* 实现摘要：新增 document domain `analysis_input.compute_analysis_input_set`（过滤已确认+有效状态版本、排除被 REPLACES 的文档、复用生效顺序确定性排序，返回有序版本 ID 列表）。
* 验证结果（2026-07-23）：4 项测试通过——固定图重复计算唯一有序集合、未确认排除、非有效状态排除、被替代文档排除；ruff、pyright 0 错误。

### C-024 实现文件替代关系命令

* 实现摘要：新增 DocumentRelationRepository 端口 + SqlAlchemy 适配器、CreateDocumentRelationUseCase（校验两文件同项目、禁止自引用、REPLACES 关系经 DFS 环检测拒绝循环替代；关系独立追加不改版本）。
* 验证结果（2026-07-23）：5 项测试通过——替代关系创建、循环替代拒绝、跨项目拒绝、自引用拒绝、关系不覆盖版本；全量 279 项通过；ruff、pyright 0 错误。

### C-023 实现文件生效顺序规则

* 实现摘要：新增 document domain `effect_order.compute_effect_order`（按发布日期升序、版本号升序、版本 ID 兜底，确定性稳定排序，无日期排最后，返回 1-based 序号）。
* 验证结果（2026-07-23）：4 项测试通过——重复计算顺序一致、更早发布优先、无日期排最后、同日期按版本号打破并列；ruff、pyright 0 错误。

### C-022 实现文件发布日期确认

* 实现摘要：DocumentVersion 增 set_published_date（naive datetime 抛 NaiveBusinessTimeError）；DocumentVersionRepository 增 get/save；新增 ConfirmPublishedDateUseCase。
* 验证结果（2026-07-23）：3 项测试通过——带时区日期成功、无时区日期被领域层拒绝（NaiveBusinessTimeError）、未知版本 NotFound；全量 270 项通过；ruff、pyright 0 错误。

### C-021 实现文件业务类型确认

* 实现摘要：Document 实体改为可变并增加 confirm_business_type + is_business_type_confirmed（OTHER 视为未确认）；DocumentRepository 增 save；新增 ConfirmDocumentTypeUseCase（命令 business_type 为枚举，非法值由 Pydantic 边界拒绝）。
* 验证结果（2026-07-23）：4 项测试通过——确认更新类型且 confirmed=True、未确认(OTHER) 不进分析输入、可重新修正类型、未知文件 NotFound；全量 267 项通过；ruff、pyright 0 错误。

### C-020 定义 FileSecurityScanner 端口

* 实现摘要：document application 新增 SecurityScanResult（CLEAN/SUSPICIOUS）、SecurityScanOutcome、FileSecurityScanner Protocol（scan 返回扫描结果）。纯接口。
* 验证结果（2026-07-23）：3 项测试通过——端口模块不依赖杀毒 SDK、Protocol 可被实现满足、扫描结果枚举区分；ruff、pyright 0 错误。

### C-019 实现 quarantine 状态流转

* 实现摘要：DocumentVersion 增加 `security_cleared` 安全门与 `clear_security()`（仅 VALIDATING 可放行）；`mark_ready` 在未放行时抛 PermissionError，保证未完成安全检查的版本不能进入 READY（SPEC.md 第 11.1 节）。
* 验证结果（2026-07-23）：新增/调整测试共 7 项通过——未放行 mark_ready 被拒且状态不变、放行后可 READY、安全放行仅 VALIDATING 允许、纯状态机非法转换仍被拒；全量 260 项通过；ruff、pyright 0 错误。

### C-018 实现同项目重复文件规则

* 实现摘要：新增 document domain `duplicate_policy.assert_not_duplicate`（同项目相同 SHA-256 抛 DuplicateFileError，跨项目/跨哈希放行）；complete_upload 改用该策略。
* 验证结果（2026-07-23）：3 项策略测试通过——同项目同哈希首次放行/第二次拒绝、跨项目同哈希放行、同项目不同哈希放行；complete_upload 回归 4 项仍通过；ruff、pyright 0 错误。

### C-017 实现上传完成接入用例

* 实现摘要：新增 Document/DocumentVersion 仓储端口 + SqlAlchemy 适配器（含 next_version_number、exists_by_sha256_in_project）、Document 领域实体、DuplicateFileError（code DUPLICATE_FILE），以及 `complete_upload.py` 用例：串联对象校验→类型/完整性/压缩校验→SHA-256→重复检测，全部通过后才移动对象 quarantine→original 并创建 Document+DocumentVersion(STORED)+标记会话完成；校验失败无任何业务变更/对象移动，DB 异常时回滚并尽力移回隔离区。
* 验证结果（2026-07-23）：4 项测试通过——成功创建版本并移动对象（STORED、original 分区、quarantine→original）、文件类型不一致无残留（无 Document/Version、对象未移动）、同哈希重复拒绝（仅 1 版本）、未知会话 NotFound；全量 255 项通过；ruff、pyright 0 错误。

### C-016 建立 DocumentRelation 迁移

* 实现摘要：新增 domain `DocumentRelationType`（REPLACES/SUPPLEMENTS/REFERENCES）、infrastructure `DocumentRelationModel`（project_id/source/target 外键 + 禁止自引用 CHECK 约束）与迁移 0006。
* 验证结果（2026-07-23）：3 项测试通过——表结构、自引用 CHECK 约束存在、插入自引用关系被数据库拒绝（IntegrityError）；ruff、pyright 0 错误。

### C-015 建立 DocumentVersion 迁移

* 实现摘要：新增 infrastructure `DocumentVersionModel`（核心原始元数据 + 处理态字段、document_id 外键、(document_id,version_number) 唯一索引、sha256 索引）与迁移 0005；domain `DocumentVersion` 实体（核心字段以只读 property 暴露无 setter，状态机方法仅改 status/canonical/page_count）。
* 验证结果（2026-07-23）：5 项测试通过——表结构、(document_id,version_number) 唯一索引、核心字段只读（赋值抛 AttributeError）、状态转换只改 status/处理态不改核心元数据、非法转换被拒；全量 248 项通过；ruff、pyright 0 错误。

### C-014 建立 Document 迁移

* 实现摘要：新增 document domain `DocumentBusinessType`（招标文件/澄清/补遗/延期通知/附件/其他）、infrastructure `DocumentModel`（project_id 外键、business_type、name + 时间戳）与迁移 0004_create_documents。conftest engine 启用 SQLite PRAGMA foreign_keys=ON，使测试 FK 行为与生产 PG 一致；修正 upload_session 测试以先建项目满足外键。
* 验证结果（2026-07-23）：3 项测试通过——表结构与无身份字段、project_id 外键引用 projects、Document 必须归属存在项目（违反外键抛 IntegrityError）；全量 243 项通过；ruff、pyright 0 错误。

### C-013 实现 SHA-256 计算

* 实现摘要：新增 document domain `hashing.py`（sha256_hex 一次性、sha256_streaming 分片、iter_chunks 切片，结果一致）。
* 验证结果（2026-07-23）：4 项测试通过——已知值正确、大文件分片与一次性一致、不同分片大小结果一致、空输入；ruff、pyright 0 错误。

### C-012 实现压缩异常校验

* 实现摘要：新增 document domain `compression.py`（validate_compression：对 ZIP 容器检查解压后总字节数上限与压缩比上限，超限抛 CompressionBombError）与 CompressionBombError（code COMPRESSION_BOMB）。
* 验证结果（2026-07-23）：4 项测试通过——小 ZIP 通过、解压体积超限拒绝、压缩比过高拒绝、非 ZIP 不检查；ruff、pyright 0 错误。

### C-011 实现空文件与损坏文件校验

* 实现摘要：新增 document domain `file_integrity.py`（validate_file_integrity：空文件抛 EmptyFileError、PDF 缺 %%EOF 或 ZIP 中央目录损坏抛 CorruptFileError）与 EmptyFileError/CorruptFileError（codes EMPTY_FILE/CORRUPT_FILE）。
* 验证结果（2026-07-23）：5 项测试通过——空文件 EMPTY_FILE、合法 PDF/ZIP 通过、截断 PDF 与损坏 ZIP 为 CORRUPT_FILE、两类错误码互不相同；ruff、pyright 0 错误。

### C-010 实现 MIME 与文件魔数校验

* 实现摘要：新增 document domain `file_type.py`（FileFormat、detect_format 按魔数、validate_file_type 校验声明 MIME/扩展名与魔数一致，首版支持 PDF/DOCX）与 `FileTypeMismatchError`（code FILE_TYPE_MISMATCH）。
* 验证结果（2026-07-23）：7 项测试通过——PDF/DOCX 检测与校验通过、伪扩展名（ZIP 声明为 PDF）拒绝、未知魔数拒绝、MIME/扩展名不一致拒绝、扩展名带点归一化；ruff、pyright 0 错误。

### C-009 实现上传完成对象校验

* 实现摘要：ObjectStorage 端口与 MinIO 适配器补 `size(key)`（stat_object.size）；新增 document domain `exceptions.UploadObjectError`（code UPLOAD_OBJECT_INVALID）与 `application/upload_verification.py`（verify_uploaded_object：解析对象键、校验存在、校验大小与声明一致，任一不符抛错）。
* 验证结果（2026-07-23）：5 项测试通过——合法返回大小、缺失抛错、大小不符抛错、非法对象键抛错、稳定错误码；全量 220 项通过；ruff、pyright 0 错误。

### C-008 发布创建上传会话 API

* 实现摘要：新增 document api（POST /api/v1/upload-sessions → CreateUploadSessionUseCase，依赖 get_session/get_object_storage/get_settings）、bootstrap get_object_storage 依赖与 configure_object_storage。conftest 设置测试环境占位配置使 get_settings 可用；修复 env.py 仅在未显式设置 url 时读 DATABASE_URL，避免与测试迁移冲突。
* 验证结果（2026-07-23）：3 项契约测试通过——合法 201 返回上传信息且无身份字段、缺字段 422 VALIDATION_ERROR、未知项目 404 NOT_FOUND；全量 215 项通过；ruff、pyright 0 错误。

### C-007 实现创建上传会话用例

* 实现摘要：新增 document domain `upload_session.py`（UploadSession 聚合：create 工厂校验元数据与过期、can_complete/complete/expire/cancel、过期不可完成）、UploadSessionRepository 端口 + SqlAlchemy 适配器、`create_upload_session.py` 用例（校验项目存在 + 字节上限、生成 quarantine 不可猜测键、返回 presigned PUT 地址）。ObjectStorage 端口与 MinIO 适配器补 presigned_put_url。
* 验证结果（2026-07-23）：4 项测试通过——合法元数据返回短期上传信息（object_key 在 quarantine、PUT URL、PENDING 落库）、未知项目 NotFound、超限拒绝且不落库、暂存键不含原始文件名；全量 212 项通过；ruff、pyright 0 错误。

### C-006 建立 UploadSession 迁移

* 实现摘要：states 新增 UploadSessionStatus（PENDING/COMPLETED/EXPIRED/CANCELLED）与转换；新增 document `infrastructure/models.py`（UploadSessionModel：project_id 外键、declared_*、object_key、status、created_at/expires_at/completed_at）与迁移 0003_create_upload_sessions。
* 验证结果（2026-07-23）：3 项测试通过——表结构与必填列/无身份字段、project_id 外键引用 projects、可写入带过期时间的会话；全量 208 项通过；ruff、pyright 0 错误。

### C-005 实现对象移动与删除适配器

* 实现摘要：MinioObjectStorage 增加 `move(source, destination)`（copy_object 后 remove 源键）与 `delete(key)`（remove_object，幂等）。ObjectStorage 端口六方法（put/get/exists/delete/move/presigned_get_url）实现完毕。
* 验证结果（2026-07-23）：新增 2 项 mock 测试（document 共 13 项通过）——move 复制到目标键并删除源键、delete 幂等多次调用仅触发 remove_object；ruff、pyright 0 错误。

### C-004 实现短期对象授权地址

* 实现摘要：MinioObjectStorage 增加 `presigned_get_url(key, expires_in_seconds)`（经 presigned_get_object 生成短期地址，到期由 MinIO 校验）。日志脱敏（不记录完整签名 URL）在 J-003 实现。
* 验证结果（2026-07-23）：新增 1 项 mock 测试（document 共 11 项通过）——以指定有效期调用并返回地址；ruff、pyright 0 错误。

### C-003 实现对象私有读取适配器

* 实现摘要：MinioObjectStorage 增加 `get(key)`（经持凭客户端 get_object 读取全部字节并关闭/释放连接）。
* 验证结果（2026-07-23）：新增 2 项 mock 测试（共 10 项 document 测试通过）——get 以分类/键路径读取字节并释放连接、读取经后端授权通道；ruff、pyright 0 错误。运行时真实 MinIO 验证待 Docker。

### C-002 实现对象写入适配器

* 实现摘要：新增 minio 依赖与 `document/infrastructure/minio_object_storage.py`（MinioObjectStorage：put 流式上传、exists 经 stat_object，NoSuchKey→False、其它错误抛出；客户端可注入以支持 mock）。
* 验证结果（2026-07-23）：4 项 mock 单元测试通过——put 以分类/键路径与 content_type 上传固定字节、exists 存在/不存在正确、非 NoSuchKey 错误向上抛；ruff、pyright 0 错误。
* **运行时缺口**：本机无 MinIO/Docker，真实集成验证待 Docker。

### C-001 定义 ObjectStorage 端口

* 实现摘要：新增 document 模块与 `application/__init__.py`（ObjectCategory 六分区、ObjectKey 不可猜测键、ObjectStorage Protocol：put/get/exists/delete/move/presigned_get_url）。纯标准库。
* 验证结果（2026-07-23）：4 项测试通过——端口模块不导入对象存储 SDK、document domain/application 层 AST 扫描确认无 minio/boto3 等、ObjectKey 路径格式、Protocol 可被内存实现满足；ruff、pyright 0 错误。

### B-019 验证业务入口无鉴权（阶段 B 完成）

* 实现摘要：新增 `tests/architecture/test_no_auth_entry.py` 无鉴权回归护栏——不带 Token/Cookie/用户头调用健康检查与业务接口均正常（非 401/403）、应用未注册鉴权中间件、误带 Authorization 头仍正常（后端不校验身份）。
* 验证结果（2026-07-23）：4 项测试通过；阶段 B 收尾全量 192 项通过；pyright 0 错误。
* 阶段 B 总结：B-001～B-019 全部完成——Project 表/领域实体/仓储/创建-编辑-列表-归档-恢复-删除-恢复删除用例与 API 契约、OperationLog append-only 表（DB 触发器强制）+端口+适配器+命令集成（成功同事务/失败独立事务）+查询 API、无鉴权契约护栏。所有业务 API 无身份字段、无鉴权依赖。

### B-018 发布操作记录查询 API

* 实现摘要：新增 `operation_log/application/list_operation_logs.py`（OperationLogItem 无身份字段、按 resource_type/resource_id/action 筛选、按 occurred_at desc）与 `operation_log/api`（GET /api/v1/operation-logs，project_id 便捷参数等价 resource_type=project+resource_id）。
* 验证结果（2026-07-23）：4 项契约测试通过——按 project_id 筛选、按 action 筛选、响应无身份/操作者字段、分页与时间倒序；ruff、pyright 0 错误。

### B-017 接入项目命令操作记录

* 实现摘要：新增 `operation_log/application/recording.py`（record_command_outcome：成功同事务记录并提交、失败回滚后独立事务持久化 failure+错误码；录制器可选，未注入仅负责提交/回滚）。重构 6 个项目用例（create/edit/archive/restore/delete/recover）经该编排产出操作记录，注入 session_factory+open_recorder。pyproject 忽略 UP047（与 UP046 一致保留 TypeVar 泛型写法）。
* 验证结果（2026-07-23）：4 项集成测试通过——create 成功 1 条 success、create 失败 1 条 failure(INVALID_PROJECT_DATA) 且独立持久化、6 个命令各 1 条 success、NotFound 1 条 failure(NOT_FOUND)；全量 184 项通过；ruff、pyright 0 错误。重构未破坏既有用例测试。

### B-016 实现操作记录写入适配器

* 实现摘要：新增 `operation_log/infrastructure/recorder.py`（SqlAlchemyOperationRecorder 实现 OperationRecorder 端口，暂存 INSERT 到 append-only 表，不在内部提交）。
* 验证结果（2026-07-23）：3 项测试通过——成功记录动作/资源/时间/结果齐全、失败记录含错误码、适配器不在内部提交（未提交前新会话查不到、提交后可见）；ruff、pyright 0 错误。

### B-015 定义操作记录端口

* 实现摘要：新增 `operation_log/application/__init__.py`（OperationRecord frozen dataclass + OperationRecorder Protocol，纯标准库）。
* 验证结果（2026-07-23）：3 项测试通过——端口模块 AST 扫描确认仅依赖标准库（无 sqlalchemy/fastapi/logging 等）、OperationRecord 不可变、Protocol 可被任意实现满足；ruff、pyright 0 错误。

### B-014 建立 OperationLog 迁移

* 实现摘要：新增 operation_log 模块与 `OperationLogModel`（id/request_id/action/resource_type/resource_id/result/error_code/occurred_at，无身份字段、无 updated_at）。迁移 0002 建表并按 dialect 创建 append-only 触发器（SQLite RAISE(ABORT) 与 PG 触发器函数），数据库层强制禁止 UPDATE/DELETE。
* 验证结果（2026-07-23）：4 项测试通过——表存在且结构正确/无身份字段、追加成功、UPDATE 与 DELETE 均被触发器拒绝（IntegrityError）；全量 174 项通过；ruff、pyright 0 错误。

### B-013 实现待删除项目恢复

* 实现摘要：新增 domain `PENDING_DELETION_RETENTION_DAYS=30` 与 `pending_deletion_deadline()`；新增 `PreconditionFailedError`（412）；新增 `application/recover_project.py`（到期前恢复，到期/超过抛 PreconditionFailedError）。仓储读取时间戳增加 `_ensure_aware` 规整（SQLite 不保留时区，按 UTC 还原；PG 无影响）。
* 验证结果（2026-07-23）：4 项测试通过——到期前（29 天）恢复成功、到期点与之后均拒绝、未知 NotFound、到期边界 2026-07-23+30d=2026-08-22；全量 170 项通过；ruff、pyright 0 错误。

### B-012 实现项目待删除标记

* 实现摘要：新增 `application/delete_project.py`（DeleteProjectCommand/UseCase：载入→404→request_deletion()→save→提交，进入 PENDING_DELETION 并记录 pending_deletion_at）。
* 验证结果（2026-07-23）：3 项测试通过——删除后状态 PENDING_DELETION 且 pending_deletion_at 有值、数据未物理清除（记录数仍 1）、不在活动列表、归档项目也可删除、未知 NotFound；ruff、pyright 0 错误。

### B-011 实现项目恢复用例

* 实现摘要：新增 `application/restore_project.py`（RestoreProjectCommand/UseCase：载入→404→restore_from_archive()→save→提交，非法转换由状态机拒绝）。
* 验证结果（2026-07-23）：2 项测试通过——恢复后状态 ACTIVE、字段（名称/地区）保持不变并重回活动列表、未知项目 NotFound；ruff、pyright 0 错误。

### B-010 实现项目归档用例

* 实现摘要：新增 `application/archive_project.py`（ArchiveProjectCommand/UseCase：载入→404→archive()→save→提交）。
* 验证结果（2026-07-23）：3 项测试通过——归档后默认列表不可见但数据仍存（状态 ARCHIVED）、未知项目 NotFound、按 ARCHIVED 过滤可列出归档；ruff、pyright 0 错误。

### B-009 发布项目列表 API 契约

* 实现摘要：在 project 路由增加 GET /api/v1/projects（page/page_size/sort/status 查询参数，page_size 受 MAX_PAGE_SIZE 上限，sort 解析 "field:direction"，status 过滤）。
* 验证结果（2026-07-23）：5 项契约测试通过——分页返回正确 Page、page_size>上限返回 422、page<1 返回 422、sort=name 升序正确、status=ARCHIVED 过滤生效；全量 158 项通过；ruff、pyright 0 错误。

### B-008 实现项目列表投影

* 实现摘要：新增 `application/list_projects.py`（ProjectListItem 投影 + list_projects 只读查询：状态过滤默认 ACTIVE、排序字段白名单映射、DB 级 offset/limit、无显式排序时按 updated_at 降序稳定）。
* 验证结果（2026-07-23）：5 项测试通过——翻页稳定无重叠遗漏、按 name 升/降序正确、归档项目默认排除、只读投影不写表（前后记录数不变）；ruff、pyright 0 错误。

### B-007 发布项目编辑 API 契约

* 实现摘要：在 project 路由增加 PATCH /api/v1/projects/{project_id}（EditProjectRequest body：expected_version + 可选字段，路径取 project_id），调用 EditProjectUseCase。
* 验证结果（2026-07-23）：4 项契约测试通过——正确版本 200 返回结果、版本冲突 409 CONFLICT problem+json、未知项目 404 NOT_FOUND、空白字段 400 INVALID_PROJECT_DATA；ruff、pyright 0 错误。

### B-006 实现项目编辑用例

* 实现摘要：新增 `application/edit_project.py`（EditProjectCommand 含 project_id/expected_version/可选字段、EditProjectUseCase：载入→404/版本冲突校验→update_details→save→提交）。乐观并发在用例层以 expected_version 比对当前 version 实现，冲突抛 ConflictError。
* 验证结果（2026-07-23）：4 项测试通过——正确版本编辑成功 version+1、过期 expected_version 抛 ConflictError 且不覆盖较新数据、未知项目 NotFound、空白字段被领域拒绝且不改数据；ruff、pyright 0 错误。

### B-005 发布项目创建 API 契约

* 实现摘要：新增 `modules/project/api/__init__.py`（POST /api/v1/projects → CreateProjectUseCase，201）、`bootstrap/db.get_session` 依赖与 configure_session_factory。配套重构错误架构以支持统一映射：抽取纯 `shared/error_codes.ErrorCode` 与纯 `shared/domain_error.DomainError` 基类；errors.py 改为导入并再导出，NotFoundError/ConflictError、state_transitions.InvalidTransitionError、project.InvalidProjectDataError 均继承纯 DomainError；处理器新增 RequestValidationError → 422 VALIDATION_ERROR Problem Details。
* 验证结果（2026-07-23）：`tests/modules/project/test_project_api.py` 4 项契约测试通过——合法请求 201 且响应键集合与落库正确、缺字段 422 VALIDATION_ERROR、空白字段 400 INVALID_PROJECT_DATA、OpenAPI 含创建接口；全量 140 项通过；ruff、pyright 0 错误。重构未破坏既有测试。

### B-004 实现项目创建用例

* 实现摘要：新增 `application/create_project.py`（CreateProjectCommand Pydantic 命令 min_length=1、CreateProjectResult、CreateProjectUseCase 编排领域工厂+仓储+事务提交）。
* 验证结果（2026-07-23）：6 项测试通过——最小合法输入创建并落库回读、4 类必填字段空串被 Pydantic 拒绝、空白字符串被领域非空不变量拒绝且不落库；ruff、pyright 0 错误。

### B-003 实现 Project 仓储

* 实现摘要：新增 application 端口 `ProjectRepository`（Protocol：add/get/save）与 infrastructure `SqlAlchemyProjectRepository`（领域 Project↔ProjectModel 映射、不持事务）。新增 `tests/conftest.py` 提供 SQLite+迁移 engine/session 夹具供后续 DB 测试复用。
* 验证结果（2026-07-23）：`uv run pytest tests/modules/project/test_project_repository.py` 4 项通过——创建后按 id 回读字段一致、事务回滚不留数据（新会话亦查不到）、未知 id 返回 None、save 保存归档变更与 version；全量 130 项通过；ruff、pyright 0 错误。

### B-002 建立 Project 领域实体

* 实现摘要：新增 `modules/project/domain/project.py`（Project 聚合：create 工厂、字段非空不变量、archive/restore/request_deletion/recover/purge/update_details 命令，经 `validate_transition` 校验、version 自增、Clock 可注入）与 `domain/exceptions.py`（纯 `InvalidProjectDataError`）。纯领域层，不依赖框架。
* 验证结果（2026-07-23）：`uv run pytest tests/modules/project` 10 项通过——空字段被拒（参数化 4 类）、归档/恢复/删除/恢复/清除流转正确、purge-from-active 与 archive-from-deleted 非法转换抛 InvalidTransitionError、update_details 校验+version 自增；全量 126 项通过；ruff、pyright 0 错误。

### B-001 建立 Project 数据迁移

* 实现摘要：建立数据库层基础设施——`shared/orm.py`（DeclarativeBase + 命名约定 + TimestampMixin，可移植类型）、`bootstrap/db.py`（engine/session 工厂）、`modules/project/infrastructure/models.py`（ProjectModel：UUID 主键、name/region/industry/project_type、lifecycle_state、archived_at/pending_deletion_at/deleted_at、乐观 version，无身份字段）。建立 Alembic 脚手架（alembic.ini/ASCII、env.py 从 DATABASE_URL 读连接串并导入各模块 Model、script.py.mako）与首个迁移 0001_create_projects。在 states.py/state_transitions.py 补 ProjectLifecycleStatus 状态机与转换。将 A-024 身份字段扫描由正则改为 AST 标识符扫描，避免注释误判。
* 验证结果（2026-07-23）：`uv run pytest tests/migrations` 4 项通过——空库迁移创建 projects 表、含核心列与 version、无身份字段、可回滚；全量 116 项通过；ruff、pyright 0 错误。
* **运行时缺口（诚实记录）**：本机无 PostgreSQL/Docker，迁移以临时文件 SQLite 作“空库”运行验证（可移植类型保证 PG 兼容）；生产目标 PostgreSQL，真实 PG 迁移待 Docker 就绪补充。

### A-024 验证首版无身份模块（阶段 A 完成）

* 实现摘要：新增 `tests/architecture/test_no_identity.py`，作为长期护栏：扫描确认 modules/ 下无身份业务模块目录、源码无 organization_id/user_id/tenant_id/created_by/reviewed_by 身份字段、无 User/Organization/Tenant/Membership/Role/Session/Account 身份实体类定义。
* 验证结果（2026-07-23）：`uv run pytest tests/architecture/test_no_identity.py` 3 项通过。阶段 A 收尾全量 112 项测试通过。
* 阶段 A 总结：A-001～A-024 全部完成——单仓骨架、Python/React 工程、健康入口、四层分层与依赖规则、UUID/时间/金额分值/分页/追踪/错误共享内核、强类型配置、Ruff+Pyright+pytest/Vitest 质量门、PostgreSQL/Redis/MinIO/OTel 开发 Compose（结构验证，运行时待 Docker）、14 份 ADR、集中状态机与转换验证器、模块 README 模板、无身份护栏。

### A-023 建立模块 README 模板

* 实现摘要：新增 `docs/module-readme-template.md`（职责/入口/状态/依赖/禁区五小节模板与复制说明），并据此为示例模块补 `modules/example/README.md`。新增 `tests/docs/test_module_readme.py` 验证。
* 验证结果（2026-07-23）：`uv run pytest tests/docs/test_module_readme.py` 3 项通过——模板与示例 README 均含五小节、模板含使用说明。

### A-022 实现状态转换通用验证器

* 实现摘要：新增纯模块 `shared/state_transitions.py`，集中维护各状态机合法转换边（依据 SPEC 第 5.2～5.5、6.16 节）与 `validate_transition`/`is_valid_transition`，非法转换抛稳定 `InvalidTransitionError`（code=INVALID_STATE_TRANSITION）。更新 `shared/errors.py`：problem_from_error 与 FastAPI 处理器显式将 InvalidTransitionError 映射为 409 Problem Details。
* 验证结果（2026-07-23）：`uv run pytest tests/shared/test_state_transitions.py` 7 项通过；全量 106 项通过；ruff、pyright 0 错误。合法转换静默通过，非法转换（含未知状态机）抛稳定错误，API 映射为 409 INVALID_STATE_TRANSITION。

### A-021 定义集中状态机目录

* 实现摘要：新增 `shared/states.py`，集中定义七个状态机（DocumentVersionStatus、PageStatus、AnalysisRunStatus、AnalysisRunCompleteness、AnalysisTaskStatus、ReviewStatus、ReportSnapshotStatus）与 STATE_MACHINES 注册表，严格对应 SPEC.md 第 5.2～5.5、6.16 节。
* 验证结果（2026-07-23）：`uv run pytest tests/shared/test_states.py` 10 项通过——各机成员与 SPEC 一致、机名唯一、机内成员唯一、AST 扫描确认七个枚举类在全代码库各定义一次（无重复定义）；ruff 通过。

### A-020 建立 ADR 记录集

* 实现摘要：新增 `docs/adr/` 下 ADR-001～ADR-014 共 14 份记录（对应 PLAN.md 第 4 节）与索引 README，每份含状态、日期、背景、决策、后果、重评条件。新增 `tests/docs/test_adr.py` 结构验证。
* 验证结果（2026-07-23）：`uv run pytest tests/docs` 4 项通过——14 份 ADR 齐全、每份含背景/决策/后果/重评条件、含状态与日期、索引引用全部 14 份。

### A-019 建立 OpenTelemetry 开发服务

* 实现摘要：新增 `infra/otel-collector-config.yaml`（OTLP gRPC/HTTP 接收器、batch 处理、debug 导出器、health_check 扩展、traces/metrics 管线）与 Compose 中 otel_collector 服务（挂载配置、4317/4318/13133 仅回环）。
* 验证结果（2026-07-23）：`uv run pytest tests/infra` 7 项结构验证通过（collector 服务挂载配置、端口回环、配置含 otlp 接收器与 traces 管线）。运行时 Trace 接收验证待 Docker。

### A-018 建立 MinIO 开发服务

* 实现摘要：在 Compose 增加 minio 服务（mc ready 健康检查、minio_data 卷、端口仅回环）与 minio_init 一次性容器（依赖 minio 健康、`mc mb` 建桶并 `mc anonymous set none` 显式私有）。env 示例补充 MinIO 变量。
* 验证结果（2026-07-23）：`uv run pytest tests/infra` 6 项结构验证通过（含 minio 健康检查、初始化容器依赖与显式私有策略）。运行时“未签名不可读”验证待 Docker。

### A-017 建立 Redis 开发服务

* 实现摘要：在 `infra/docker-compose.dev.yml` 增加 redis:7 服务（redis-cli ping 健康检查、appendonly 持久化、redis_data 命名卷、端口仅回环），并补充结构验证。
* 验证结果（2026-07-23）：`uv run pytest tests/infra` 5 项结构验证通过。运行时“连接/写入/读取/重启”验证待 Docker。

### A-016 建立 PostgreSQL 开发服务

* 实现摘要：新增 `infra/docker-compose.dev.yml`（postgres:17，pg_isready 健康检查、命名数据卷 postgres_data、端口仅绑定 127.0.0.1、可经环境变量覆盖凭据）与 `infra/.env.dev.example`。新增 `tests/infra/test_compose.py` 对 Compose 做结构验证。
* 验证结果（2026-07-23）：`uv run pytest tests/infra` 4 项结构验证通过（YAML 合法、postgres 服务含健康检查与持久卷、端口仅回环、命名卷声明）；ruff 通过。
* **运行时验证缺口（诚实记录）**：本机环境未安装 Docker，任务定义的运行时验证“重启后测试数据仍存在”尚未执行；配置已提供命名持久卷与 unless-stopped 策略以保证该行为，待 Docker 环境就绪后补充 `docker compose up/down` 重启持久化验证。

### A-015 建立前端质量检查配置

* 实现摘要：新增 `vitest.config.ts`（jsdom 环境、globals=false、@别名、setupFiles）、`src/test/setup.ts`（jest-dom 匹配器 + 显式 afterEach cleanup）、`src/App.test.tsx`（Testing Library 渲染断言）。package.json 增加 vitest/@testing-library/jsdom 依赖与 `test` 脚本。
* 验证结果（2026-07-22）：`npm run typecheck` 退出 0；`npm run build` 退出 0；`npm run test` 2 项通过。类型、构建、组件测试命令分别运行通过。

### A-014 建立后端质量检查配置

* 实现摘要：在 `pyproject.toml` 增加 Ruff 配置（line-length 100、target py312、规则集 E/F/I/UP/B/SIM/C4，忽略 B008 与 UP046）与 Pyright 配置（standard 模式、src 范围、.venv）。应用 lint 后修复：未用导入（DefaultGreetingPolicy 显式继承端口）、`str,Enum`→StrEnum、长行（SortableItem 别名）、pyright 的 get_settings reportCallIssue 定向豁免与排序键 cast。
* 验证结果（2026-07-22）：三条命令分别运行——`uv run ruff check src tests` 全部通过；`uv run pyright` 0 错误；`uv run pytest -q` 78 项通过。验证通过。

### A-013 建立强类型配置

* 实现摘要：新增 `bootstrap/config.py`（Pydantic Settings，关键基础设施连接 DB/Redis/S3/DeepSeek 为必填、密钥用 SecretStr、文件与页数限额强类型带默认、`max_project_pages=500` 业务硬限制、`accept_new_analysis` 发布接单开关、`get_settings()` 缓存）与 `backend/.env.example` 环境变量示例。
* 验证结果（2026-07-22）：`uv run pytest tests/bootstrap` 5 项通过。缺少 database_url 时 ValidationError 明确失败退出；完整配置加载；默认值生效；密钥 SecretStr 不泄漏；限额可经环境变量覆盖。验证通过。

### A-012 定义统一错误契约

* 实现摘要：新增 `shared/errors.py`，定义稳定错误码目录 `ErrorCode`、领域错误基类 `DomainError` 及子类（NotFound/Conflict/StateTransition）、RFC 7807 风格 `ProblemDetail`（type/title/status/detail/error_code/instance/trace_id）、`problem_from_error` 映射（非领域异常归 INTERNAL_ERROR 不泄漏细节）与 `add_problem_exception_handler` FastAPI 处理器（返回 application/problem+json）。
* 验证结果（2026-07-22）：`uv run pytest tests/shared` 56 项通过。NotFound 与 Conflict 两个示例失败返回字段结构一致、按 error_code/status 判定不匹配文案；未知异常归 INTERNAL_ERROR 且不泄漏敏感细节；FastAPI 处理器返回 problem+json。验证通过。

### A-011 定义请求追踪上下文

* 实现摘要：新增 `shared/request_context.py`，基于 contextvars 提供 `RequestContext`（request_id 必填、trace_id 可选回退为 request_id）、`from_headers`（X-Request-ID 与 W3C traceparent）、`set/reset/current` 与 `request_context_scope` 上下文管理器，使 API 层设置的追踪标识在应用用例中可直接读取。
* 验证结果（2026-07-22）：`uv run pytest tests/shared` 52 项通过。API 设置上下文后用例读取同一 request_id；作用域退出后恢复 None 不泄漏；trace_id 回退、header 解析、traceparent 提取均正确。验证通过。

### A-010 定义分页契约

* 实现摘要：新增 `shared/pagination.py`，定义 `PageRequest`（page>=1、page_size∈[1,MAX_PAGE_SIZE=100]、offset）、`SortField`/`SortDirection`、`apply_sort`（利用 Python 稳定排序做多键可复现排序）、泛型 `Page[T]`（items/total/total_pages）。Pydantic 契约。
* 验证结果（2026-07-22）：`uv run pytest tests/shared` 45 项通过。越界页大小（0/-1/>100/10000）被 ValidationError 拒绝；单/多键排序稳定可复现、升降序正确；总页数计算正确。验证通过。

### A-009 定义金额与分值值对象

* 实现摘要：新增 `shared/money.py`（`Money`：Decimal 承载、拒绝 float、量化到分 ROUND_HALF_UP、币别校验与四则运算）与 `shared/score.py`（`Score`：Decimal、拒绝 float 与负值、加法保持精确性用于评分闭合）。稳定错误 `MoneyError`/`ScoreError`。
* 验证结果（2026-07-22）：`uv run pytest tests/shared` 31 项通过；0.1+0.2=0.3、0.1+0.2+0.3=0.6 无浮点误差；float 输入、负分值、币别不一致均被稳定拒绝。验证通过。

### A-008 定义业务时间值对象

* 实现摘要：新增 `shared/business_time.py`，定义业务时区常量 `BUSINESS_TIMEZONE`（Asia/Shanghai）、`BusinessInstant` 值对象（强制带时区，构造即拒绝 naive 输入，`in_business_timezone()` 确定性转换，`now(clock)` 可注入）、`NaiveBusinessTimeError`（code=`NAIVE_BUSINESS_TIME`）与 `Clock` 端口 + `SystemClock` 实现。仅依赖标准库 datetime/zoneinfo。
* 主要新增文件：`shared/business_time.py`、`tests/shared/test_business_time.py`、`TASKS.md`、`PROGRESS.md`。
* 验证命令：`uv run pytest tests/shared -q`。
* 验证结果（2026-07-22）：18 项共享测试通过（10 UUID + 8 时间）。naive 输入抛稳定错误；UTC 00:00→业务时区 08:00+08:00 固定；Clock 注入可控 now()。验证通过。
* Git commit：本次提交单独记录 `A-008`。

### A-007 定义 UUID 值对象

* 实现摘要：新增 `tender_insight/shared/` 共享内核包与 `shared/identifiers.py`，提供 `Uuid` 值对象（frozen dataclass，`new()`、`from_str()`、标准字符串表示、可哈希可排序）与稳定错误 `InvalidUuidError`（code=`INVALID_UUID`）。仅依赖标准库 uuid，可被 domain 层安全导入。
* 主要新增文件：`shared/__init__.py`、`shared/identifiers.py`、`tests/shared/__init__.py`、`tests/shared/test_identifiers.py`、`TASKS.md`（勾选 `A-007`）、`PROGRESS.md`。
* 验证命令：`uv run pytest tests/shared -q`。
* 验证结果（2026-07-22）：10 项测试通过——合法 UUID 往返一致、带连字符与紧凑形式等价、5 类非法输入均抛 `InvalidUuidError`、稳定错误码存在、可哈希可排序。验证通过。
* Git commit：本次提交单独记录 `A-007`。
* 架构检查：值对象仅依赖标准库；稳定错误码而非文案；无身份残留或魔法常量。

### A-006 建立模块依赖检查

* 实现摘要：建立分层依赖规则的唯一权威实现 `tests/architecture/dependency_rules.py`（AST 扫描 + 层级判定 + 违例收集），将 A-005 内联的导入扫描重构为单一来源；规则覆盖“低层不得反向依赖高层”（domain 不导入 application/infrastructure/api、application 不导入 infrastructure/api、infrastructure 不导入 api）与 domain 禁止第三方框架/SDK。`test_layering.py` 改为委托该权威实现；新增 `test_dependency_rules.py` 用临时源码根做受控注入验证。
* 主要新增/修改文件：`tests/architecture/dependency_rules.py`、`tests/architecture/test_dependency_rules.py`、`tests/architecture/test_layering.py`（重构）、`TASKS.md`（勾选 `A-006`）、`PROGRESS.md`。
* 验证命令：`uv run pytest -q`。
* 验证结果（2026-07-22）：全部 17 项后端测试通过。`test_reverse_dependency_is_detected_when_injected` 注入 domain→application 反向依赖后检出恰好 1 条违例（失败），`test_passes_after_reverse_dependency_removed` 移除后通过，`test_allowed_forward_dependencies_pass` 正向依赖通过。注入失败、移除通过，验证通过。
* Git commit：本次提交单独记录 `A-006` 交付物与进度更新。
* 架构检查：规则检查器仅依赖标准库，不耦合被检对象；导入扫描逻辑仅此一处，无重复。

### A-005 建立后端模块分层模板

* 实现摘要：建立 `tender_insight/modules/` 与参考样例模块 `modules/example/`，固化 domain / application / infrastructure / api 四层分层。domain（`greeting.py`）用标准库 dataclasses 建模值对象与领域服务，不导入任何框架；application 定义 `GreetingPolicy` 端口（Protocol）与 `greet` 用例；infrastructure 提供 `DefaultGreetingPolicy` 内存适配器；api 提供 `create_router()` 演示业务路由挂载方式（默认不挂入主应用，避免污染生产 API）。新增 `tests/architecture/test_layering.py`（AST 扫描 domain 源文件，断言不导入 Web/ORM/队列/供应商 SDK）与 `tests/modules/test_example.py`（四层端到端协作）。
* 主要新增文件：`modules/__init__.py`、`modules/example/__init__.py`、`modules/example/domain/{__init__,greeting}.py`、`modules/example/application/__init__.py`、`modules/example/infrastructure/__init__.py`、`modules/example/api/__init__.py`、`tests/architecture/{__init__,test_layering}.py`、`tests/modules/{__init__,test_example}.py`、`TASKS.md`（勾选 `A-005`）、`PROGRESS.md`。
* 验证命令：`uv run pytest -q`。
* 验证结果（2026-07-22）：全部 14 项后端测试通过，其中 `test_domain_does_not_import_forbidden_frameworks` 与 `test_example_domain_uses_pure_stdlib_modeling` 直接证明示例 domain 不导入 Web、ORM、队列或供应商 SDK。验证通过。
* Git commit：本次提交单独记录 `A-005` 交付物与进度更新。
* 架构检查：domain 不依赖任何框架；端口定义在 application；依赖方向 api→application→domain 与 infrastructure→application/domain 一致；未引入身份残留或魔法常量。

### A-004 初始化 React 工程

* 实现摘要：在 `frontend/` 下建立 Vite + React 19 + TypeScript 最小应用：`package.json`、`vite.config.ts`（含 `@`→src 别名与开发代理 `/api`、`/health` 到后端 8000）、`tsconfig`（project references，strict，`@/*` 路径别名）、`index.html`、`src/main.tsx`、`src/App.tsx`、`src/vite-env.d.ts`。根 `.gitignore` 补充 `dist/` 与 `*.tsbuildinfo`。首版无登录/会话 UI。
* 主要新增文件：`frontend/package.json`、`frontend/package-lock.json`、`frontend/vite.config.ts`、`frontend/tsconfig.json`、`frontend/tsconfig.app.json`、`frontend/tsconfig.node.json`、`frontend/index.html`、`frontend/src/main.tsx`、`frontend/src/App.tsx`、`frontend/src/vite-env.d.ts`、`.gitignore`、`TASKS.md`（勾选 `A-004`）、`PROGRESS.md`。
* 验证命令：`npm install`、`npm run typecheck`（`tsc -b --noEmit`）、`npm run build`（`tsc -b && vite build`）。
* 验证结果（2026-07-22）：`npm install` 安装 69 包、0 漏洞；`npm run typecheck` 退出码 0；`npm run build` 退出码 0，产物 `dist/index.html` + `dist/assets/index-*.js`（28 模块，gzip 61KB）。类型检查与生产构建分别成功。验证通过。
* Git commit：本次提交单独记录 `A-004` 交付物与进度更新。
* 架构检查：未引入身份/鉴权 UI；未提前引入 TanStack Query、Ant Design 等阶段 I 依赖；严格模式 TypeScript，避免 any。

### A-003 建立后端最小启动入口

* 实现摘要：新增 `tender_insight/main.py`，提供应用工厂 `create_app()` 与模块级 ASGI 对象 `app`，注册独立的 `/health` 健康检查路由，返回由 `HealthResponse`（Pydantic 模型）定义的固定契约 `{status:"ok", service:"tender-insight-api", version}`。按 SPEC.md 第 6.1 节，健康检查不挂在 `/api/v1` 业务前缀下；首版无鉴权，入口不含登录/会话中间件。
* 主要新增文件：`backend/src/tender_insight/main.py`、`backend/tests/test_health.py`、`TASKS.md`（勾选 `A-003`）、`PROGRESS.md`。
* 验证命令：`uv run pytest -q`（TestClient 契约测试）；真实进程冒烟 `uvicorn tender_insight.main:app --port 8765` 后 `curl /health`。
* 验证结果（2026-07-22）：全部 6 项后端测试通过（3 冒烟 + 3 健康契约：固定契约、模型可解析、健康路由与业务路由分离）；真实 uvicorn 进程启动后 `curl http://127.0.0.1:8765/health` 返回 `{"status":"ok","service":"tender-insight-api","version":"0.1.0"}`，HTTP 200。验证通过。
* Git commit：本次提交单独记录 `A-003` 交付物与进度更新。
* 架构检查：健康检查不依赖数据库/对象存储/外部模型；不引入身份、鉴权或魔法常量；未提前挂载业务路由。

### A-002 初始化 Python 工程

* 实现摘要：在 `backend/` 下建立 `pyproject.toml`（hatchling 构建、src 布局、包名 `tender_insight`、`requires-python = ">=3.12,<4"`）、`.python-version`（3.12）、包骨架 `src/tender_insight/__init__.py`、测试包 `tests/` 与冒烟测试，以及根 `.gitignore`。声明阶段 A/B/D 所需核心运行时依赖（FastAPI、uvicorn、Pydantic 2、pydantic-settings、SQLAlchemy 2、Alembic、psycopg 3、Celery 5、redis、httpx、structlog、jinja2）与 dev 组（pytest、pytest-asyncio、ruff、pyright）。重型 OCR/文档/报告依赖按任务边界推迟到阶段 E/H。通过 `python -m pip install uv` 安装 uv 0.11.31。
* 主要新增文件：`backend/pyproject.toml`、`backend/.python-version`、`backend/src/tender_insight/__init__.py`、`backend/tests/__init__.py`、`backend/tests/test_smoke.py`、`backend/uv.lock`、`.gitignore`、`TASKS.md`（勾选 `A-002`）、`PROGRESS.md`。
* 验证命令：`uv lock`、`uv sync --frozen`、`uv run pytest -q`。
* 验证结果（2026-07-22）：`uv lock` 解析 58 个包并写出 `uv.lock`，uv 自动按 `.python-version` 拉取 CPython 3.12.13；`uv sync --frozen` 在全新虚拟环境中按锁文件安装成功；`uv run pytest -q` 3 项冒烟测试全部通过（包可导入、核心运行时依赖可导入、Python 基线 >=3.12 满足）。验证通过。
* Git commit：本次提交单独记录 `A-002` 交付物与进度更新。
* 架构检查：未引入跨模块耦合、隐式状态、身份残留或魔法常量；未提前实现 A-003 入口或 A-005 分层。

### A-001 创建单仓目录骨架

* 实现摘要：严格按 `PLAN.md` 第 3.1 节在仓库根目录创建 `frontend/`、`backend/`、`evaluation/`、`infra/`、`docs/` 五个顶层目录，每个目录放一份说明其职责、技术基线和边界的 `README.md`，使空目录可被 Git 追踪且边界可核对。本任务只建立目录边界，不初始化 Python（`A-002`）、React（`A-004`）或基础设施（阶段 A 开发服务）内容。
* 主要修改/新增文件：`frontend/README.md`、`backend/README.md`、`evaluation/README.md`、`infra/README.md`、`docs/README.md`、`TASKS.md`（勾选 `A-001`）、`PROGRESS.md`。
* 验证命令：`ls -1`、`git ls-files --others --exclude-standard`、`test -d frontend backend evaluation infra docs`。
* 验证结果（2026-07-22）：五个目录全部存在且与 `PLAN.md` 第 3.1 节一致；`git ls-files --others --exclude-standard` 仅显示五个目录下的 `README.md`，无业务代码跨目录混放、无 `pyproject.toml` 或 React 工程文件等后续任务内容。验证通过。
* Git commit：本次提交单独记录 `A-001` 交付物与进度更新。
* 架构检查：未引入跨模块 ORM 写入、隐式状态、身份权限残留或魔法常量；未预埋用户/组织/角色/Token/RBAC/租户兼容分支。

---

`TASKS.md` 共有 326 个原子任务，已完成 74 个（`A-001`～`A-024`、`B-001`～`B-019`、`C-001`～`C-032`），剩余 252 个。

已完成的非开发里程碑：

* 实现摘要：形成并提交需求规格、技术实施计划、原子任务清单、MVP 技术架构和初始进度记录。
* 主要修改文件：`SPEC.md`、`PLAN.md`、`TASKS.md`、`四川建筑施工招标文件智能解读与投标风险提示系统-MVP技术架构.md`、原 `PROGRESS.md`。
* Git commit：`ce7eb988b94b6855b4c7a4d97c4f7a6e3a65753a`（`docs: 文档更新`）。
* 验证命令：`git show --format=fuller --name-status --stat ce7eb98`、`git ls-tree -r --name-only HEAD`。
* 验证结果：上述 5 份文档均由该提交新增并存在于当前 HEAD；这只是文档基线验证，未执行代码测试、类型检查、Lint 或构建。

## 4. 待完成任务

按照当前依赖关系和实际可执行顺序：

1. `A-002 初始化 Python 工程`（当前任务）

   * 前置依赖：`A-001`（已完成）。
   * 主要工作：建立 `backend/pyproject.toml` 与 uv 锁文件。
   * 验收标准：空环境按锁文件安装成功。

2. `A-004 初始化 React 工程`

   * 前置依赖：`A-001`（已完成）。
   * 主要工作：建立 Vite/React/TypeScript 最小应用。
   * 验收标准：前端类型检查和生产构建分别通过。

3. `A-003 建立后端最小启动入口`、`A-005 建立后端模块分层模板`、`A-013 建立强类型配置`、`A-014 建立后端质量检查配置`、`A-015 建立前端质量检查配置`

   * 前置依赖：按 `TASKS.md` 分别依赖 `A-002` 或 `A-004`。
   * 主要工作：建立最小可运行入口、分层模板、配置边界以及可分别执行的质量检查。
   * 验收标准：严格采用各任务在 `TASKS.md` 中定义的单一交付物和独立验证，不合并任务完成证据。

4. 阶段 A 剩余任务 `A-006` 至 `A-024`

   * 前置依赖：逐项遵循 `TASKS.md` 依赖列；只在依赖满足后实施。
   * 主要工作：依赖检查、共享值对象、错误与追踪契约、开发基础设施、ADR、集中状态机和无身份模块约束。
   * 验收标准：阶段 A 的 API、空 Worker、前端、依赖规则、状态测试和空库迁移达到 `PLAN.md` 的完成条件。

5. 后续阶段 `B` 至 `L`

   * 前置依赖：主顺序为 `A → B → C → D → E → F → G → H → I → J → K → L`；阶段内并行仅在依赖列已经满足时进行。
   * 主要工作：依次完成项目边界、文件版本、异步底座、解析证据、知识与模型网关、领域分析、复核报告、桌面端、可观测性与生命周期、Linux 部署、验收交付。
   * 验收标准：每个任务的单一交付物、独立验证、错误边界、中文注释和架构检查全部满足后才可勾选；最终以 `SPEC.md` 第 15 章人工验收为准。

完整的 326 项任务、名称、依赖和独立验证要求以 `TASKS.md` 为唯一任务清单，本文不复制整表。

## 5. 已知问题和风险

### 根目录缺少 `CLAUDE.md`

* 影响：用户要求新会话优先读取该文件，但当前文件系统、未忽略文件扫描和当前 Git 树中都不存在 `CLAUDE.md`，因此无法核对其中可能存在的项目级指令。
* 当前结论：这是已确认的恢复资料缺口；现有 `SPEC.md`、`PLAN.md` 和 `TASKS.md` 已足以确定 `A-001` 的交付物与验证要求，因此缺口不阻止该任务。
* 建议处理方式：新会话开始时再次执行 `Test-Path .\CLAUDE.md` 和 `git ls-files -- CLAUDE.md`；若文件后来出现，必须先完整阅读再编码。除非用户另行要求，不在本任务中创建该文件。

### 尚无可运行工程和自动化验证入口

* 影响：目前不能执行单元测试、集成测试、类型检查、Lint、构建、迁移或运行时验证，任何功能完成声明都没有代码证据。
* 当前结论：这是项目尚处于阶段 A 起点的正常事实，不是测试通过。
* 建议处理方式：从 `A-001` 开始按原子任务建立工程和质量检查；对应工具真实可运行并通过后，再更新验证勾选项。

### 后续外部运行依赖尚未落地

* 影响：PostgreSQL、Redis、MinIO、LibreOffice、PaddleOCR、中文字体、WeasyPrint、DeepSeek 配置和 Linux 目标环境会影响后续阶段验证。
* 当前结论：`SPEC.md` 第 17 章明确部分部署参数为非阻塞参数；当前没有证据表明这些依赖已经可用。
* 建议处理方式：仅在相应任务依赖到达时按 `TASKS.md` 建立和验证，不提前用 Mock、fallback 或魔法常量掩盖缺失依赖。

### 开发环境缺少 `uv` 与 `docker`（本会话确认）

* 影响：`A-002` 的交付物明确要求 `backend/pyproject.toml` 与 **uv 锁文件**，而当前环境未安装 `uv`（`uv --version` 返回未找到）。`A-016/A-017/A-018/A-019` 要求通过 Docker Compose 提供 PostgreSQL、Redis、MinIO、OpenTelemetry，而当前环境未安装 `docker`。后续阶段还需 LibreOffice（`E-002`）、PaddleOCR（`E-012`）、DeepSeek 真实调用（`F-024`）、WeasyPrint（`H-016`）和 Linux 服务器（阶段 K）。
* 当前结论：这是运行环境约束，不是代码缺陷。在受限环境下优先交付可在当前环境真实验证的产物（纯领域代码、配置文件、单元测试、前端构建），并对每个任务如实记录“已执行的验证”与“因外部依赖未就绪而待执行的验证”，不通过删除测试、跳过断言或伪造通过来规避。
* 建议处理方式：`A-002` 起尝试用 `pip install uv` 或等价方式安装 `uv`；若仍不可用，则生成 `pyproject.toml` 并以 `pip` 在虚拟环境中安装依赖作为等价验证，同时保留 uv 作为生产锁文件工具的配置意图，在进度中明确说明。

### Python 解释器版本与计划基线不一致

* 影响：当前环境为 Python 3.14.4，`PLAN.md` 锁定 Python 3.12。
* 当前结论：不影响 `A-001`；在 `A-002` 初始化时将通过 `requires-python` 固定基线，并尽量选择同时兼容 3.12/3.14 的依赖版本，避免把解释器差异写死成业务行为。
* 建议处理方式：以 `requires-python = ">=3.12,<4"` 等约束声明基线；运行时若发现 3.14 不兼容某依赖，记录到本节并按 `TASKS.md` 第 1 节原则处理，不静默降级。

## 6. 失败尝试和重要决策

### 当前没有已确认的失败实现尝试

* 尝试内容：仓库尚未开始编码，没有代码、测试或 Git 记录能够证明发生过实现失败尝试。
* 结果：无可记录的开发失败方案。
* 失败原因或选择理由：不得把聊天过程、读取工具问题或计划性讨论写成项目开发失败。
* 后续是否应继续使用：不适用；后续出现可复现失败时，记录最小方案、原因和禁止重复条件。

### Python 模块化单体作为唯一后端基线

* 尝试内容：`SPEC.md` 和 `PLAN.md` 明确后端采用 Python 3.12、FastAPI、SQLAlchemy 2、Celery，并在单仓内实施模块化单体。
* 结果：已形成规划基线并由提交 `ce7eb98` 提交。
* 失败原因或选择理由：原需求分析中的 NestJS、Prisma 等旧技术建议已失效；模块化单体用于保持边界清晰，同时避免首版微服务复杂度。
* 后续是否应继续使用：是；不得重新引入旧技术栈兼容层或跨模块 ORM 写入。

### 单工作区且无应用鉴权

* 尝试内容：首版不建立用户、组织、成员、角色、会话、Token、RBAC、租户字段或 RLS，生产访问交由可信网络边界控制。
* 结果：已写入 `SPEC.md`、`PLAN.md` 和 `TASKS.md` 的范围、架构与验收约束。
* 失败原因或选择理由：身份与多租户明确不在 MVP 范围；未来引入时应作为新版本重新设计，不预埋兼容分支。
* 后续是否应继续使用：是；不要重复实现登录、权限或伪造操作者身份。

### 状态事实与证据链必须显式分离

* 尝试内容：PostgreSQL 作为业务状态唯一事实来源；文件接入、分析运行、任务和完整性使用独立状态；候选、正式结果和人工结果分别保存。
* 结果：已在需求、计划和任务清单中形成一致约束。
* 失败原因或选择理由：避免 Redis/Celery/前端缓存成为隐式状态，避免模型输出直接写正式结论或人工结果覆盖系统原结果。
* 后续是否应继续使用：是；不得用单字段混合状态、静默 fallback 或无证据结论替代该设计。

## 7. 阻塞事项

* 环境约束（非代码缺陷）：`uv`、`docker` 未安装，详见第 5 节。这些影响后续需要锁文件或容器化基础设施的任务的“自动验证”，但不阻止先编写代码、配置和可在当前环境运行的测试。

## 8. 下一步执行计划

1. 开始 `A-002 初始化 Python 工程`：在 `backend/` 下创建 `pyproject.toml`，固定 Python 与依赖基线；尝试安装 `uv` 生成锁文件，若不可用则以虚拟环境 `pip install` 作为等价验证并如实记录。
2. 随后按依赖推进 `A-003`、`A-005`、`A-013`、`A-014`、`A-015` 等阶段 A 任务。
3. 每完成一个任务：执行其独立验证、勾选 `TASKS.md`、更新 `PROGRESS.md`、创建单独 Git commit，并按 `TASKS.md` 第 14 节做架构检查。

## 9. 验证状态

* [ ] 单元测试通过（尚无工程）
* [ ] 集成测试通过（尚无工程）
* [ ] 类型检查通过（尚无工程）
* [ ] Lint 通过（尚无工程）
* [ ] 构建通过（尚无工程）
* [ ] 核心功能人工验证通过（尚无业务功能）
* [x] Git diff 已审查（A-001 交付物与文档变更）
* [x] 无调试代码和临时文件
* [x] 无敏感信息
* [ ] 所有修改已提交（A-001 提交中）

说明：前六项没有对应工程或执行结果，因此保持未勾选。“Git diff 已审查”“无调试代码和临时文件”“无敏感信息”描述本次 `A-001` 改动的实际检查结果，不代表业务系统验收完成。

## 10. 新会话恢复指令

新会话先完整阅读 `CLAUDE.md`（若存在；当前已确认缺失）、`SPEC.md`、`PLAN.md`、`TASKS.md`、`PROGRESS.md`，再检查 `git status --short --branch`、`git log -5 --oneline --decorate --stat`、`git diff` 和 `git diff --cached`。以代码、测试、Git 和任务勾选为事实来源，不把规划里程碑算作开发任务完成。当前应从 `A-002 初始化 Python 工程` 继续。开始编码前先执行：

```bash
git status --short --branch
git log -5 --oneline --decorate
git diff --stat
git diff --cached --stat
test -f CLAUDE.md && echo "CLAUDE.md exists" || echo "CLAUDE.md missing"
rg -n '^\| \[[ x]\] [A-L]-\d{3} \|' TASKS.md
uv --version 2>&1; docker --version 2>&1; python --version 2>&1; node --version 2>&1
```
