"""example 模块基础设施层。

实现 application 声明的端口。本层“可以”依赖外部库（ORM、对象存储、模型
SDK 等），但不被 domain/application 直接导入；依赖方向始终是 infrastructure
→ application/domain。

本参考样例提供一个内存适配器，演示端口实现的位置与方式。
"""

from __future__ import annotations

from tender_insight.modules.example.application import GreetingPolicy


class DefaultGreetingPolicy:
    """默认问候策略适配器（内存实现）。

    实际业务模块的适配器在此处接入数据库、对象存储或模型网关；此处仅返回
    固定消息，保持样例最小化且可脱离外部依赖运行。
    """

    DEFAULT_MESSAGE: str = "工程已就绪，等待业务接入"

    def message_for(self, subject: str) -> str:  # noqa: D401 - 端口实现
        # 忽略 subject 差异，返回固定消息；真实策略可按主体差异化返回。
        return self.DEFAULT_MESSAGE
