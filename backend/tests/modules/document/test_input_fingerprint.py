"""分析输入版本指纹测试（C-026 独立验证）。

验证同集合重排后指纹不变，内容变化后指纹变化。
"""

from __future__ import annotations

from tender_insight.modules.document.domain.input_fingerprint import (
    compute_input_fingerprint,
)


def test_order_independent() -> None:
    """同集合不同输入顺序得到相同指纹。"""
    members = [("v1", "a" * 64), ("v2", "b" * 64)]
    assert compute_input_fingerprint(members) == compute_input_fingerprint(reversed(members))


def test_content_change_changes_fingerprint() -> None:
    """成员内容（sha256）变化后指纹变化。"""
    base = [("v1", "a" * 64), ("v2", "b" * 64)]
    changed = [("v1", "a" * 64), ("v2", "c" * 64)]
    assert compute_input_fingerprint(base) != compute_input_fingerprint(changed)


def test_membership_change_changes_fingerprint() -> None:
    base = [("v1", "a" * 64), ("v2", "b" * 64)]
    removed = [("v1", "a" * 64)]
    assert compute_input_fingerprint(base) != compute_input_fingerprint(removed)


def test_empty_set_stable() -> None:
    assert compute_input_fingerprint([]) == compute_input_fingerprint([])
    assert compute_input_fingerprint([])


def test_distinct_sets_distinct_fingerprints() -> None:
    a = [("v1", "a" * 64)]
    b = [("v2", "a" * 64)]
    assert compute_input_fingerprint(a) != compute_input_fingerprint(b)
