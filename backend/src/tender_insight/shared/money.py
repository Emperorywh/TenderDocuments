"""金额值对象（A-009）。

SPEC.md 第 7.2 节要求金额使用 Decimal，与 PostgreSQL NUMERIC 对应；
第 9.3 节将金额归入确定性规则（不得主要依赖模型）。本模块强制以 Decimal
承载金额并拒绝 float 输入，避免二进制浮点误差进入业务与财务口径。

人民币金额统一精确到分（0.01），采用 ROUND_HALF_UP 舍入，符合国内财务惯例。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# 人民币最小计量单位：分。
_MONEY_QUANTUM = Decimal("0.01")
DEFAULT_CURRENCY = "CNY"


class MoneyError(ValueError):
    """金额相关稳定错误基类。"""

    code: str = "INVALID_MONEY"


class Money:
    """人民币金额值对象。

    内部以 Decimal 存储，构造时拒绝 float 与非法输入，运算结果统一量化到分。
    通过私有构造 + 工厂方法 from_yuan 暴露构造入口，确保所有金额都经过校验。
    """

    __slots__ = ("_amount", "_currency")

    def __init__(self, amount: Decimal, currency: str = DEFAULT_CURRENCY) -> None:
        # 内部构造假定 amount 已是合法 Decimal；外部构造请使用 from_yuan。
        if not isinstance(amount, Decimal):
            raise MoneyError("金额内部构造必须使用 Decimal")
        if not currency or not isinstance(currency, str):
            raise MoneyError("币别不能为空")
        # 量化到分，保证比较与存储口径一致。
        self._amount = amount.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)
        self._currency = currency

    @classmethod
    def from_yuan(cls, raw: str | int | Decimal, currency: str = DEFAULT_CURRENCY) -> Money:
        """从元构造金额；拒绝 float，避免 0.1 这类值的二进制误差。

        接受字符串（推荐，如 "1234.56"）、整数（按元）与 Decimal；
        float 必须由调用方先转为字符串，强制在边界处消除浮点。
        """
        if isinstance(raw, float):
            raise MoneyError("金额禁止直接使用 float，请传入字符串或 Decimal")
        try:
            amount = Decimal(raw)
        except (ArithmeticError, ValueError) as cause:
            raise MoneyError(f"非法金额：{raw!r}") from cause
        if not amount.is_finite():
            raise MoneyError(f"金额必须有限：{raw!r}")
        return cls(amount, currency)

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def currency(self) -> str:
        return self._currency

    def add(self, other: Money) -> Money:
        if other._currency != self._currency:
            raise MoneyError(f"币别不一致：{self._currency} 与 {other._currency}")
        return Money(self._amount + other._amount, self._currency)

    def subtract(self, other: Money) -> Money:
        if other._currency != self._currency:
            raise MoneyError(f"币别不一致：{self._currency} 与 {other._currency}")
        return Money(self._amount - other._amount, self._currency)

    def multiply(self, factor: str | int | Decimal) -> Money:
        """金额乘以系数（如数量、比例）；系数同样禁止 float。"""
        if isinstance(factor, float):
            raise MoneyError("金额乘数禁止使用 float")
        return Money(self._amount * Decimal(factor), self._currency)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Money)
            and self._currency == other._currency
            and self._amount == other._amount
        )

    def __hash__(self) -> int:
        return hash((self._amount, self._currency))

    def __lt__(self, other: Money) -> bool:
        if other._currency != self._currency:
            raise MoneyError("比较金额要求币别一致")
        return self._amount < other._amount

    def __str__(self) -> str:
        return f"{self._amount} {self._currency}"
