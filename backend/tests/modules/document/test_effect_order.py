"""文件生效顺序规则测试（C-023 独立验证）。

验证相同输入在重复计算时顺序一致，且按发布日期/版本号稳定排序。
"""

from __future__ import annotations

from datetime import UTC, datetime

from tender_insight.modules.document.domain.effect_order import (
    EffectOrderInput,
    compute_effect_order,
)
from tender_insight.shared.identifiers import Uuid


def _input(date: datetime | None, version: int) -> EffectOrderInput:
    return EffectOrderInput(version_id=Uuid.new(), published_date=date, version_number=version)


def test_deterministic_across_repeated_calls() -> None:
    """相同输入（任意顺序）重复计算结果一致。"""
    a = _input(datetime(2026, 7, 1, tzinfo=UTC), 1)
    b = _input(datetime(2026, 7, 5, tzinfo=UTC), 1)
    c = _input(None, 2)

    order1 = compute_effect_order([a, b, c])
    order2 = compute_effect_order([c, b, a])
    assert order1 == order2


def test_earlier_published_date_ranks_first() -> None:
    """更早发布的版本优先级更高（序号小）。"""
    a = _input(datetime(2026, 7, 1, tzinfo=UTC), 1)
    b = _input(datetime(2026, 7, 5, tzinfo=UTC), 1)
    order = compute_effect_order([b, a])
    assert order[a.version_id] == 1
    assert order[b.version_id] == 2


def test_missing_date_ranks_last() -> None:
    a = _input(datetime(2026, 7, 1, tzinfo=UTC), 1)
    nodate = _input(None, 1)
    order = compute_effect_order([nodate, a])
    assert order[a.version_id] == 1
    assert order[nodate.version_id] == 2


def test_same_date_breaks_tie_by_version_number() -> None:
    date = datetime(2026, 7, 1, tzinfo=UTC)
    v1 = _input(date, 1)
    v2 = _input(date, 2)
    order = compute_effect_order([v2, v1])
    assert order[v1.version_id] == 1
    assert order[v2.version_id] == 2
