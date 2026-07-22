"""example 模块领域模型与规则（纯领域层）。

刻意使用标准库 dataclasses 而非 Pydantic，以演示领域层不绑定校验框架；
业务领域值对象在各业务模块中按需选择实现方式，但必须保持本层不依赖
Web、ORM、队列或供应商 SDK。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# 表示用户称呼的合法取值；以常量集合表达领域约束，避免散落魔法字符串。
VALID_TITLES: Final[frozenset[str]] = frozenset({"先生", "女士", "团队"})


class InvalidGreetingTitle(ValueError):
    """称呼不在领域允许集合内时抛出的领域异常。

    领域异常派生自内置 ValueError，保证领域层不依赖任何框架专属异常基类。
    """


@dataclass(frozen=True)
class GreetingText:
    """问候文本值对象。

    不可变（frozen）以避免在应用层传递过程中被无意修改；构造时即完成
    领域校验，使非法状态无法被创建（fail fast）。
    """

    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if not stripped:
            # 空文本不是合法问候，直接拒绝构造。
            raise InvalidGreetingTitle("问候文本不能为空")
        # frozen dataclass 需通过 object.__setattr__ 在 __post_init__ 中改值。
        object.__setattr__(self, "value", stripped)


@dataclass(frozen=True)
class Greeting:
    """完整问候聚合：称呼 + 被问候主体 + 文本。"""

    title: str
    subject: str
    text: GreetingText

    def __post_init__(self) -> None:
        if self.title not in VALID_TITLES:
            raise InvalidGreetingTitle(f"不支持的称呼：{self.title}")
        if not self.subject.strip():
            raise InvalidGreetingTitle("被问候主体不能为空")


def compose_greeting(title: str, subject: str, message: str) -> Greeting:
    """领域服务：按称呼与主体组装一条问候。

    领域服务是无状态纯函数，仅依赖领域类型与规则，便于脱离框架独立测试。
    """
    text = GreetingText(f"{title}，{subject}：{message}")
    return Greeting(title=title, subject=subject.strip(), text=text)
