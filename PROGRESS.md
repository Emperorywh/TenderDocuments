# 项目进度

## 1. 当前总体状态

* 当前阶段：阶段 B 进行中；`B-001`～`B-009` 已完成，下一任务 `B-010`。
* 整体完成度：`33 / 326` 个原子开发任务完成（约 `10.1%`）。
* 当前分支：`main`，HEAD 为 `dfc8182`（B-008 提交）。
* 最后更新时间：2026-07-22（Asia/Shanghai）。
* 当前是否存在阻塞：是（环境约束，详见第 5 节）。`A-002` 要求 uv 锁文件，而当前环境未安装 `uv`；后续阶段 B/C/D/E/F 还需要 Docker、PostgreSQL、Redis、MinIO、LibreOffice、PaddleOCR、DeepSeek、WeasyPrint、Linux 等。在受限环境下优先构建可在当前环境验证的代码与配置，并在本文件如实记录哪些验证已执行、哪些因外部依赖未就绪而待执行。

已确认的仓库状态：

* 在 `A-001` 之前，仓库只有 6 份 Markdown 文档；`A-001` 新增 `frontend/`、`backend/`、`evaluation/`、`infra/`、`docs/` 五个顶层目录，各含一份说明职责边界的 `README.md`。
* `TASKS.md` 中 `A-001` 已勾选 `[x]`，其余 325 个任务仍为 `[ ]`。

## 2. 当前任务

* Task 编号：`B-010`
* Task 名称：实现项目归档用例
* 当前状态：待开始。
* 前置依赖：`B-002`、`B-003`（已完成）。
* 当前目标：实现归档命令。
* 验收标准：归档后默认列表不可见且数据未删除。

需要持续遵守的约束：

* 全新系统，不兼容旧代码或旧数据，不引入 legacy、灰度、fallback、deprecated 或兼容分支。
* 首版为单实例、单工作区、无应用鉴权；禁止预埋用户、组织、角色、Token、RBAC、多租户字段或 RLS。
* 采用模块化单体和显式分层；领域层不得依赖 FastAPI、Celery、SQLAlchemy 或模型 SDK。
* PostgreSQL 是业务状态唯一事实来源；Redis、Celery 和前端缓存不承载权威业务状态。
* 新增或修改代码必须使用必要的多行简体中文注释；不得主动格式化既有代码；不得自动启动浏览器测试。

## 3. 已完成任务

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

`TASKS.md` 共有 326 个原子任务，已完成 33 个（`A-001`～`A-024`、`B-001`～`B-009`），剩余 293 个。

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
