"""分页与排序契约测试（A-010 独立验证）。

验证越界页大小被拒绝、排序结果稳定。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tender_insight.shared.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Page,
    PageRequest,
    SortDirection,
    SortField,
    apply_sort,
)


def test_defaults() -> None:
    req = PageRequest()
    assert req.page == 1
    assert req.page_size == DEFAULT_PAGE_SIZE
    assert req.sort == []
    assert req.offset == 0


def test_offset_computation() -> None:
    req = PageRequest(page=3, page_size=20)
    assert req.offset == 40


@pytest.mark.parametrize("bad_size", [0, -1, MAX_PAGE_SIZE + 1, 10_000])
def test_page_size_out_of_range_rejected(bad_size: int) -> None:
    """越界页大小被拒绝。"""
    with pytest.raises(ValidationError):
        PageRequest(page=1, page_size=bad_size)


@pytest.mark.parametrize("bad_page", [0, -1])
def test_page_must_be_positive(bad_page: int) -> None:
    with pytest.raises(ValidationError):
        PageRequest(page=bad_page)


def test_max_page_size_allowed() -> None:
    """恰好等于上限的页大小被接受。"""
    req = PageRequest(page=1, page_size=MAX_PAGE_SIZE)
    assert req.page_size == MAX_PAGE_SIZE


def test_sort_single_field_ascending_stable() -> None:
    """单字段升序，等值项保持原相对顺序（稳定）。"""
    items = [
        {"id": 1, "risk": "HIGH"},
        {"id": 2, "risk": "LOW"},
        {"id": 3, "risk": "HIGH"},
        {"id": 4, "risk": "MEDIUM"},
    ]
    result = apply_sort(items, [SortField(field="risk", direction=SortDirection.ASC)])
    risks = [r["risk"] for r in result]
    # HIGH 排前，且 id=1 仍先于 id=3（稳定）。
    assert risks == ["HIGH", "HIGH", "LOW", "MEDIUM"]
    assert [r["id"] for r in result if r["risk"] == "HIGH"] == [1, 3]


def test_sort_multi_key_deterministic() -> None:
    """多键排序结果可复现：先按 risk，再按 id。"""
    items = [
        {"id": 2, "risk": "HIGH"},
        {"id": 1, "risk": "HIGH"},
        {"id": 3, "risk": "LOW"},
    ]
    sorts = [
        SortField(field="risk", direction=SortDirection.ASC),
        SortField(field="id", direction=SortDirection.ASC),
    ]
    once = apply_sort(items, sorts)
    twice = apply_sort(items, sorts)
    assert once == twice
    assert [r["id"] for r in once] == [1, 2, 3]


def test_sort_descending() -> None:
    items = [{"id": 1, "v": 10}, {"id": 2, "v": 30}, {"id": 3, "v": 20}]
    result = apply_sort(items, [SortField(field="v", direction=SortDirection.DESC)])
    assert [r["v"] for r in result] == [30, 20, 10]


def test_page_response_total_pages() -> None:
    page = Page[dict](items=[{"x": 1}], total=45, page=2, page_size=20)
    assert page.total_pages == 3


def test_page_response_zero_total() -> None:
    page = Page[dict](items=[], total=0, page=1, page_size=20)
    assert page.total_pages == 0
