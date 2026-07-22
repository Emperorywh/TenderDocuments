"""可配置文件限额策略测试（C-027 独立验证）。

验证限额来自配置、修改配置即改变限制、领域无魔法常量。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tender_insight.modules.document.domain.exceptions import FileLimitExceededError
from tender_insight.modules.document.domain.file_limits import FileLimits


def _settings(**overrides: int) -> SimpleNamespace:
    base = {"max_file_bytes": 1000, "max_files_per_project": 5, "max_project_bytes": 10_000}
    base.update(overrides)
    return SimpleNamespace(**base)


def test_limits_built_from_settings() -> None:
    limits = FileLimits.from_settings(_settings())
    assert limits.max_file_bytes == 1000
    assert limits.max_files_per_project == 5
    assert limits.max_project_bytes == 10_000


def test_changing_config_changes_limits() -> None:
    """修改配置即可改变限制（领域无魔法常量）。"""
    loose = FileLimits.from_settings(_settings(max_file_bytes=9999))
    tight = FileLimits.from_settings(_settings(max_file_bytes=10))
    with pytest.raises(FileLimitExceededError):
        tight.assert_file_size(100)
    loose.assert_file_size(100)  # 放宽后通过


def test_file_size_enforced() -> None:
    limits = FileLimits.from_settings(_settings(max_file_bytes=1000))
    limits.assert_file_size(1000)
    with pytest.raises(FileLimitExceededError):
        limits.assert_file_size(1001)


def test_file_count_enforced() -> None:
    limits = FileLimits.from_settings(_settings(max_files_per_project=3))
    limits.assert_file_count(2)  # 已有 2 个，可再加 1
    with pytest.raises(FileLimitExceededError):
        limits.assert_file_count(3)  # 已达上限


def test_project_bytes_enforced() -> None:
    limits = FileLimits.from_settings(_settings(max_project_bytes=1000))
    limits.assert_project_bytes(500, 400)
    with pytest.raises(FileLimitExceededError):
        limits.assert_project_bytes(500, 600)
