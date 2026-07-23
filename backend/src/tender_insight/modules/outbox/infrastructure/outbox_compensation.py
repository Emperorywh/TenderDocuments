"""outbox 投递补偿（D-011）。

对投递失败（FAILED）的事件按指数退避重新入队：退避已过且未超过最大尝试次数的
FAILED 事件重置为 PENDING，由下轮 dispatch 重新领取投递（SPEC.md 第 11.2 节
“指数退避重试”、第 11.3 节“Outbox 允许重复投递”）。超过最大尝试次数的 FAILED
事件不再自动重投（死信，需人工处理），避免对持续不可用 broker 或毒消息无限重试。

退避秒数由纯领域规则 exponential_backoff_seconds 按各事件 attempts 计算（D-011
单一权威实现）；now 由调用方注入（可注入固定时钟，便于确定性测试）。本函数不提交，
随调度事务一起持久化。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tender_insight.modules.outbox.domain.backoff import exponential_backoff_seconds
from tender_insight.modules.outbox.infrastructure.models import OutboxEventModel

if TYPE_CHECKING:  # 仅类型注解用，避免运行期 ORM 耦合。
    from sqlalchemy.orm import Session


def _ensure_aware(value: datetime) -> datetime:
    """读取的时间戳若为 naive（SQLite 不保留时区），按 UTC 还原为 aware。

    生产 PostgreSQL 的 timestamptz 保留时区，此处理无影响；仅弥合 SQLite 测试库。
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def requeue_failed_events(
    session: Session,
    *,
    now: datetime,
    base_seconds: float,
    factor: float,
    max_seconds: float,
    max_attempts: int,
) -> int:
    """重新入队退避已过且未超 max_attempts 的 FAILED 事件（FAILED→PENDING）。

    返回本轮重新入队条数。attempts 跨重试累计保留（backoff 随之增长）；超过
    max_attempts 的 FAILED 事件保持 FAILED（死信），不自动重投。
    """
    failed_rows = (
        session.query(OutboxEventModel)
        .filter_by(delivery_status="FAILED")
        .all()
    )
    requeued = 0
    for row in failed_rows:
        # 超过最大尝试次数：死信，不再自动重投（需人工处理）。
        if row.attempts >= max_attempts:
            continue
        if row.last_attempt_at is None:
            eligible = True
        else:
            waited = (now - _ensure_aware(row.last_attempt_at)).total_seconds()
            required = exponential_backoff_seconds(
                row.attempts,
                base_seconds=base_seconds,
                factor=factor,
                max_seconds=max_seconds,
            )
            eligible = waited >= required
        if eligible:
            # 重新入队：FAILED→PENDING，保留 attempts 以延续退避增长。
            row.delivery_status = "PENDING"
            requeued += 1
    return requeued
