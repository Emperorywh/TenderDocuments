"""金额与分值值对象测试（A-009 独立验证）。

验证固定金额、分值样本无浮点误差，且非法/float 输入被稳定拒绝。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from tender_insight.shared.money import DEFAULT_CURRENCY, Money, MoneyError
from tender_insight.shared.score import Score, ScoreError


# ---------------- 金额 ----------------


def test_money_from_string_no_float_error() -> None:
    """字符串构造金额无浮点误差。"""
    m = Money.from_yuan("0.1")
    assert m.amount == Decimal("0.10")


def test_money_addition_is_exact() -> None:
    """经典浮点陷阱 0.1+0.2 在 Decimal 下严格等于 0.3。"""
    total = Money.from_yuan("0.1").add(Money.from_yuan("0.2"))
    assert total.amount == Decimal("0.30")


def test_money_rejects_float_input() -> None:
    """float 输入被稳定拒绝，避免引入二进制误差。"""
    with pytest.raises(MoneyError):
        Money.from_yuan(0.1)  # type: ignore[arg-type]


def test_money_rejects_invalid_string() -> None:
    with pytest.raises(MoneyError):
        Money.from_yuan("abc")


def test_money_quantizes_to_cents_half_up() -> None:
    """金额量化到分，采用四舍五入（ROUND_HALF_UP）。"""
    # 0.125 第三位为 5，四舍五入到分得到 0.13。
    assert Money.from_yuan("0.125").amount == Decimal("0.13")
    assert Money.from_yuan("1.234").amount == Decimal("1.23")
    assert Money.from_yuan("1.235").amount == Decimal("1.24")


def test_money_currency_mismatch_rejected() -> None:
    cny = Money.from_yuan("1.00", "CNY")
    usd = Money.from_yuan("1.00", "USD")
    with pytest.raises(MoneyError):
        cny.add(usd)


def test_money_multiply_rejects_float_factor() -> None:
    m = Money.from_yuan("10.00")
    with pytest.raises(MoneyError):
        m.multiply(1.5)  # type: ignore[arg-type]
    assert m.multiply("1.5").amount == Decimal("15.00")


def test_money_default_currency_is_cny() -> None:
    assert DEFAULT_CURRENCY == "CNY"
    assert Money.from_yuan("1.00").currency == "CNY"


# ---------------- 分值 ----------------


def test_score_sum_has_no_float_error() -> None:
    """0.1+0.2+0.3 严格等于 0.6（Decimal 无误差）。"""
    total = (
        Score.from_value("0.1").add(Score.from_value("0.2")).add(Score.from_value("0.3"))
    )
    assert total.value == Decimal("0.6")


def test_score_rejects_float() -> None:
    with pytest.raises(ScoreError):
        Score.from_value(0.1)  # type: ignore[arg-type]


def test_score_rejects_negative() -> None:
    with pytest.raises(ScoreError):
        Score.from_value("-1")


def test_score_from_decimal_and_int() -> None:
    assert Score.from_value(Decimal("5")).value == Decimal("5")
    assert Score.from_value(10).value == Decimal("10")


def test_score_zero() -> None:
    assert Score.zero().value == Decimal("0")
