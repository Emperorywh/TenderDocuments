"""单项目页数限制测试（C-028 独立验证）。

验证第 500 页允许，第 501 页被拒绝纳入分析。
"""

from __future__ import annotations

import pytest

from tender_insight.modules.document.domain.exceptions import FileLimitExceededError
from tender_insight.modules.document.domain.page_limit import assert_project_pages

MAX = 500


def test_500_pages_allowed() -> None:
    """第 500 页允许。"""
    total = assert_project_pages(400, 100, max_pages=MAX)
    assert total == 500


def test_501_pages_rejected() -> None:
    """第 501 页被明确拒绝。"""
    with pytest.raises(FileLimitExceededError):
        assert_project_pages(500, 1, max_pages=MAX)


def test_zero_adding_within_limit() -> None:
    assert assert_project_pages(500, 0, max_pages=MAX) == 500


def test_large_add_rejected() -> None:
    with pytest.raises(FileLimitExceededError):
        assert_project_pages(0, 501, max_pages=MAX)
