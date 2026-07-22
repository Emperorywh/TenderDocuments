# 示例模块（example）

> 分层结构参考样例，不实现业务能力；用于固化 domain/application/infrastructure/api 四层模板。

## 职责

- 演示四层分层与端口/适配器协作方式，供后续业务模块复制结构与命名约定；
- 不承担任何业务能力，主应用默认不挂载其路由。

## 入口

- API 路由：`/api/v1/example/greeting`（仅参考，默认不挂入 `main.py`）；
- 应用用例：`greet(title, subject, policy)`；
- 端口：`GreetingPolicy`（application 声明，由 infrastructure 实现）。

## 状态

- 本模块为参考样例，无业务状态机；
- 状态机规范见 `shared/states.py`。

## 依赖

- 上游模块：无；
- 端口：`GreetingPolicy`（Protocol）→ `DefaultGreetingPolicy`（内存适配器）；
- 共享内核：无（样例领域仅用标准库 dataclasses）。

## 禁区

- domain 不得导入 FastAPI/SQLAlchemy/Celery/Redis/供应商 SDK（A-006 守护）；
- 不得跨模块直接读写 ORM Model；
- 不引入身份/权限/租户字段或兼容分支。
