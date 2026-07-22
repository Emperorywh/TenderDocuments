"""领域模块根包。

按 PLAN.md 第 3.2 节，每个业务模块统一采用 domain / application /
infrastructure / api 四层分层。模块间只允许通过应用服务、端口、领域事件
与事务 Outbox 协作，禁止跨模块直接读写对方的 ORM Model。

实际业务模块（project、document、analysis、risk、review、report、
operation_log、knowledge）随阶段 B～H 逐个建立。本包下的 example 模块为
分层结构参考样例，不构成对外业务能力。
"""
