"""分层结构参考样例模块（A-005 交付物）。

本模块不实现任何业务能力，仅用于固化 domain / application /
infrastructure / api 四层分层模板，供后续业务模块复制结构与命名约定。

层次依赖方向（PLAN.md 第 3.2 节）：

    api ──▶ application ──▶ domain ◀── infrastructure

- domain：纯领域模型与规则，不导入 FastAPI、SQLAlchemy、Celery、Redis
  或任何供应商 SDK；
- application：编排用例，依赖 domain 与端口（抽象接口），不持有框架状态；
- infrastructure：实现端口与外部适配器，可依赖 ORM、对象存储、模型 SDK；
- api：协议转换，只组装请求上下文并调用应用用例。
"""
