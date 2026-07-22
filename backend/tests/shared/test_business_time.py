"""业务时间值对象测试（A-008 独立验证）。

验证无时区输入被拒绝、时区转换结果固定、Clock 注入可控。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tender_insight.shared.business_time import (
    BUSINESS_TIMEZONE,
    BusinessInstant,
    NaiveBusinessTimeError,
    SystemClock,
)


class FixedClock:
    """测试用固定时钟，实现 Clock 端口。"""

    def __init__(self, fixed: datetime) -> None:
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed


def test_naive_datetime_is_rejected() -> None:
    """无时区输入必须被稳定错误拒绝。"""
    naive = datetime(2026, 7, 22, 10, 0, 0)
    with pytest.raises(NaiveBusinessTimeError):
        BusinessInstant(naive)


def test_aware_datetime_accepted() -> None:
    """带时区输入被接受。"""
    aware = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
    instant = BusinessInstant(aware)
    assert instant.value == aware


def test_business_timezone_is_shanghai() -> None:
    """业务时区固定为 Asia/Shanghai。"""
    assert str(BUSINESS_TIMEZONE) == "Asia/Shanghai"


def test_utc_to_business_timezone_is_fixed() -> None:
    """UTC 时间转换为业务时区结果固定（东八区 +8）。"""
    utc_noon = datetime(2026, 7, 22, 0, 0, 0, tzinfo=UTC)
    instant = BusinessInstant(utc_noon)
    converted = instant.in_business_timezone()
    # 2026-07-22 00:00:00 UTC == 2026-07-22 08:00:00 +08:00
    assert converted == datetime(2026, 7, 22, 8, 0, 0, tzinfo=BUSINESS_TIMEZONE)
    assert converted.utcoffset().total_seconds() == 8 * 3600


def test_conversion_is_deterministic_across_calls() -> None:
    """同一瞬时多次转换结果一致。"""
    instant = BusinessInstant(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    assert instant.in_business_timezone() == instant.in_business_timezone()


def test_clock_injection_controls_now() -> None:
    """注入固定 Clock 后 now() 返回该固定时间，不依赖系统墙钟。"""
    fixed = datetime(2026, 3, 1, 9, 30, 0, tzinfo=UTC)
    instant = BusinessInstant.now(clock=FixedClock(fixed))
    assert instant.value == fixed
    assert str(instant) == "2026-03-01T17:30:00+08:00"


def test_system_clock_returns_aware() -> None:
    """系统时钟返回带时区时间。"""
    value = SystemClock().now()
    assert value.tzinfo is not None


def test_naive_error_has_stable_code() -> None:
    assert NaiveBusinessTimeError.code == "NAIVE_BUSINESS_TIME"
