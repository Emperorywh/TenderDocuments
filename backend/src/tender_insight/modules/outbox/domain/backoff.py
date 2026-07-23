"""outbox 投递退避策略（D-011，纯领域规则）。

指数退避：失败投递按尝试次数计算下次重投前的等待秒数，封顶 max_seconds，避免
对持续不可用的 broker 形成热轮询（SPEC.md 第 11.2 节“指数退避重试”、第 11.3 节
“Outbox 允许重复投递，Worker 必须幂等消费”）。

本模块仅依赖标准库，是退避规则的唯一权威实现；具体 base/factor/max 由配置注入
（不在领域层散落魔法常量），供补偿重投（requeue_failed_events）与未来任务重试
（D-020）复用同一规则来源。
"""

from __future__ import annotations


def exponential_backoff_seconds(
    attempts: int,
    *,
    base_seconds: float,
    factor: float,
    max_seconds: float,
) -> float:
    """返回第 attempts 次失败后应等待的退避秒数。

    attempts 为已发生的投递尝试次数（>=1）；退避 = base_seconds * factor^(attempts-1)，
    封顶 max_seconds。attempts<1 视为尚无失败，返回 0（立即可重投）。
    """
    if attempts < 1:
        return 0.0
    raw = base_seconds * (factor ** (attempts - 1))
    return min(raw, max_seconds)
