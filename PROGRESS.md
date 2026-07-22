# 项目进度

## 1. 当前总体状态

* 当前阶段：阶段 A——工程与架构基线；`A-001`、`A-002` 已完成，正在向 `A-003` 推进。
* 整体完成度：`2 / 326` 个原子开发任务完成（约 `0.6%`）。
* 当前分支：`main`，HEAD 为 `afd0b93`（A-001 提交）。
* 最后更新时间：2026-07-22（Asia/Shanghai）。
* 当前是否存在阻塞：是（环境约束，详见第 5 节）。`A-002` 要求 uv 锁文件，而当前环境未安装 `uv`；后续阶段 B/C/D/E/F 还需要 Docker、PostgreSQL、Redis、MinIO、LibreOffice、PaddleOCR、DeepSeek、WeasyPrint、Linux 等。在受限环境下优先构建可在当前环境验证的代码与配置，并在本文件如实记录哪些验证已执行、哪些因外部依赖未就绪而待执行。

已确认的仓库状态：

* 在 `A-001` 之前，仓库只有 6 份 Markdown 文档；`A-001` 新增 `frontend/`、`backend/`、`evaluation/`、`infra/`、`docs/` 五个顶层目录，各含一份说明职责边界的 `README.md`。
* `TASKS.md` 中 `A-001` 已勾选 `[x]`，其余 325 个任务仍为 `[ ]`。

## 2. 当前任务

* Task 编号：`A-003`
* Task 名称：建立后端最小启动入口
* 当前状态：待开始。
* 前置依赖：`A-002`（已完成）。
* 当前目标：建立 FastAPI 健康检查入口，进程启动后健康检查返回固定契约。
* 验收标准：进程启动后健康检查返回固定契约。

需要持续遵守的约束：

* 全新系统，不兼容旧代码或旧数据，不引入 legacy、灰度、fallback、deprecated 或兼容分支。
* 首版为单实例、单工作区、无应用鉴权；禁止预埋用户、组织、角色、Token、RBAC、多租户字段或 RLS。
* 采用模块化单体和显式分层；领域层不得依赖 FastAPI、Celery、SQLAlchemy 或模型 SDK。
* PostgreSQL 是业务状态唯一事实来源；Redis、Celery 和前端缓存不承载权威业务状态。
* 新增或修改代码必须使用必要的多行简体中文注释；不得主动格式化既有代码；不得自动启动浏览器测试。

## 3. 已完成任务

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

`TASKS.md` 共有 326 个原子任务，已完成 2 个（`A-001`、`A-002`），剩余 324 个。

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
