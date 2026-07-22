"""业务时间值对象与 Clock 端口（A-008）。

SPEC.md 第 7.2 节要求时间使用带时区类型，业务默认时区为 Asia/Shanghai；
第 6.10 节要求关键时间保存 Asia/Shanghai 时区。本模块提供：

- 业务时区常量 BUSINESS_TIMEZONE；
- BusinessInstant 值对象：强制带时区，拒绝 naive 输入，提供固定时区转换；
- Clock 端口与 SystemClock 实现：抽象“当前时间”，便于测试注入固定时间，
  避免业务逻辑直接耦合系统时钟。

仅依赖标准库 datetime/zoneinfo，保持可被 domain 层安全导入。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

# 业务默认时区：四川位于东八区，统一使用 Asia/Shanghai。
BUSINESS_TIMEZONE: ZoneInfo = ZoneInfo("Asia/Shanghai")


class NaiveBusinessTimeError(ValueError):
    """传入无时区的时间时抛出的稳定错误。"""

    code: str = "NAIVE_BUSINESS_TIME"


@dataclass(frozen=True)
class BusinessInstant:
    """带时区的业务时间点。

    构造即校验必须带时区（tzinfo 非空），使“无时区输入”无法成为合法状态；
    内部始终保存原始时区的 aware datetime，需要展示时再按业务时区转换。
    """

    value: datetime

    def __post_init__(self) -> None:
        if self.value.tzinfo is None:
            raise NaiveBusinessTimeError("业务时间必须带时区，拒绝 naive datetime")

    @classmethod
    def now(cls, clock: "Clock | None" = None) -> "BusinessInstant":
        """取当前业务时间；可注入 Clock 以便测试使用固定时间。"""
        active_clock = clock if clock is not None else SystemClock()
        return cls(active_clock.now())

    def in_business_timezone(self) -> datetime:
        """转换为 Asia/Shanghai 时区的 aware datetime，结果确定性可复现。"""
        return self.value.astimezone(BUSINESS_TIMEZONE)

    def __str__(self) -> str:
        return self.in_business_timezone().isoformat()


class Clock(Protocol):
    """时钟端口：抽象当前时间的获取。

    端口化便于在测试中注入固定时间，避免业务规则直接依赖系统墙钟，
    也避免把“当前时间”散落为各处 datetime.now() 魔法调用。
    """

    def now(self) -> datetime:
        """返回带时区的当前时间。"""
        ...


class SystemClock:
    """Clock 端口的系统实现：以 UTC 获取当前时间。"""

    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc)
