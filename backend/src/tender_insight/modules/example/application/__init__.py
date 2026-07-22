"""example 模块应用层。

承载用例编排，依赖领域层与端口（抽象接口）。端口定义放在 application
层，使领域层不必感知“将被谁实现”；基础设施层在 application 之外实现端口。
"""

from __future__ import annotations

from typing import Protocol

from tender_insight.modules.example.domain.greeting import Greeting, compose_greeting


class GreetingPolicy(Protocol):
    """问候策略端口。

    端口是抽象：application 只声明需要“根据上下文决定消息文本”的能力，
    不关心其由内存实现、数据库实现还是模型实现。这样领域与应用逻辑与
    具体基础设施解耦，便于替换与测试。
    """

    def message_for(self, subject: str) -> str:
        """返回针对指定主体的问候消息文本。"""
        ...


def greet(
    *,
    title: str,
    subject: str,
    policy: GreetingPolicy,
) -> Greeting:
    """问候用例：按策略取消息，再交给领域服务组装问候。

    用例负责编排（取消息 + 组装），不包含领域规则本身；规则在 domain 层。
    传入 policy 而非在函数内 new 一个实现，体现依赖注入与可测试性。
    """
    message = policy.message_for(subject)
    return compose_greeting(title=title, subject=subject, message=message)
