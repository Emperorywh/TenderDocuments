# backend

后端模块化单体应用目录。

## 职责

承载 FastAPI API、领域与应用逻辑、SQLAlchemy 仓储、Celery 任务投递与适配器，以及四川规则包。PostgreSQL 是业务状态唯一事实来源。

## 技术基线

依据 `PLAN.md` 第 2.2、2.3 节：Python 3.12、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、psycopg 3、Celery 5、redis-py、HTTPX、uv、pytest、Ruff、Pyright；文档与 AI 侧使用 LibreOffice、PyMuPDF、pdfplumber、PaddleOCR、DeepSeek、Jinja2、WeasyPrint。

## 内部分层

依据 `PLAN.md` 第 3.1、3.2 节，`src/modules` 下每个领域模块采用 `domain / application / infrastructure / api` 分层：

- `domain`：不依赖 Web、ORM、队列和供应商 SDK；
- `application`：编排用例、事务、幂等和跨模块协作；
- `infrastructure`：实现仓储和外部端口；
- `api`：只做协议转换、请求上下文和用例调用。

`domain` 层不得导入 FastAPI、Celery、SQLAlchemy 或模型 SDK。

具体工程初始化见 `TASKS.md` 的 `A-002` 及后续后端任务。
