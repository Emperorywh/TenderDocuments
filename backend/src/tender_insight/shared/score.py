"""分值值对象（A-009）。

SPEC.md 第 6.9 节要求评分使用 Decimal 计算已识别总分并与声明总分比较；
第 9.3 节将分值归入确定性规则。本模块以 Decimal 承载分值，拒绝 float 与
负值，加法保持 Decimal 精确性（0.1 + 0.2 + 0.3 严格等于 0.6），用于评分
总分闭合等需要无误差累加的场景。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


class ScoreError(ValueError):
    """分值相关稳定错误。"""

    code: str = "INVALID_SCORE"


@dataclass(frozen=True)
class Score:
    """评分分值值对象。

    value 为 Decimal，构造时拒绝 float 与负值；加法不强制量化，保留 Decimal
    精确性以便多档分值累加后与满分精确比较（评分闭合，见 G-020）。
    """

    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise ScoreError("分值必须为 Decimal")
        if not self.value.is_finite():
            raise ScoreError("分值必须有限")
        if self.value < 0:
            raise ScoreError(f"分值不能为负：{self.value}")

    @classmethod
    def from_value(cls, raw: str | int | Decimal) -> Score:
        """从原始值构造分值；拒绝 float，避免二进制浮点误差。"""
        if isinstance(raw, float):
            raise ScoreError("分值禁止直接使用 float，请传入字符串或 Decimal")
        try:
            return cls(Decimal(raw))
        except (ArithmeticError, ValueError) as cause:
            raise ScoreError(f"非法分值：{raw!r}") from cause

    def add(self, other: Score) -> Score:
        """累加分值，保持 Decimal 精确性。"""
        return Score(self.value + other.value)

    @classmethod
    def zero(cls) -> Score:
        return cls(Decimal("0"))

    def __str__(self) -> str:
        return str(self.value)
