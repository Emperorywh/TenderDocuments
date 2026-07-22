"""UUID 值对象测试（A-007 独立验证）。

验证合法值往返一致、非法值被稳定错误拒绝。
"""

from __future__ import annotations

import uuid

import pytest

from tender_insight.shared.identifiers import InvalidUuidError, Uuid


def test_new_generates_valid_uuid() -> None:
    """new() 产生合法且唯一的 UUID。"""
    a = Uuid.new()
    b = Uuid.new()
    assert a != b
    assert isinstance(a.value, uuid.UUID)


def test_roundtrip_is_consistent() -> None:
    """str -> from_str -> str 往返一致，且与原对象相等。"""
    original = Uuid.new()
    reparsed = Uuid.from_str(str(original))
    assert reparsed == original
    assert str(reparsed) == str(original)


def test_accepts_standard_and_compact_forms() -> None:
    """带连字符与 32 位紧凑形式解析后等价。"""
    canonical = "123e4567-e89b-12d3-a456-426614174000"
    compact = canonical.replace("-", "")
    assert Uuid.from_str(canonical) == Uuid.from_str(compact)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not-a-uuid",
        "123",
        "gggggggggggggggggggggggggggggggg",  # 非十六进制字符
        "123e4567-e89b-12d3-a456-42661417400z",
    ],
)
def test_invalid_input_raises_stable_error(raw: str) -> None:
    """各类非法输入均抛出固定的 InvalidUuidError，而非其它异常或静默通过。"""
    with pytest.raises(InvalidUuidError):
        Uuid.from_str(raw)


def test_invalid_error_has_stable_code() -> None:
    """稳定错误码存在，供错误契约映射（无需依赖文案）。"""
    assert InvalidUuidError.code == "INVALID_UUID"


def test_uuid_is_hashable_and_orderable() -> None:
    """值对象可作为字典键、集合元素并参与稳定排序。"""
    a = Uuid.from_str("00000000-0000-0000-0000-000000000001")
    b = Uuid.from_str("00000000-0000-0000-0000-000000000002")
    assert {a, b} == {a, b}
    assert sorted([b, a]) == [a, b]
    assert a < b
