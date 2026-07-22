"""同项目哈希重复领域策略测试（C-018 独立验证）。

验证同项目相同哈希不创建第二个有效版本；跨项目相同哈希不互斥。
"""

from __future__ import annotations

import pytest

from tender_insight.modules.document.domain.duplicate_policy import assert_not_duplicate
from tender_insight.modules.document.domain.exceptions import DuplicateFileError
from tender_insight.shared.identifiers import Uuid


def test_duplicate_in_same_project_rejected() -> None:
    seen: dict[tuple[Uuid, str], bool] = {}

    def exists(pid: Uuid, sha: str) -> bool:
        return seen.get((pid, sha), False)

    project = Uuid.new()
    digest = "a" * 64

    # 首次：不存在，通过。
    assert_not_duplicate(project, digest, exists)
    seen[(project, digest)] = True

    # 第二次：同项目同哈希，拒绝。
    with pytest.raises(DuplicateFileError):
        assert_not_duplicate(project, digest, exists)


def test_same_hash_different_project_allowed() -> None:
    """跨项目相同哈希不互斥（各自保留独立业务引用，SPEC.md 第 6.4 节）。"""
    project_a = Uuid.new()
    project_b = Uuid.new()
    digest = "b" * 64
    seen = {(project_a, digest): True}  # A 项目已有

    # B 项目同哈希：不视为重复。
    assert_not_duplicate(project_b, digest, lambda pid, sha: seen.get((pid, sha), False))


def test_different_hash_same_project_allowed() -> None:
    project = Uuid.new()
    seen = {(project, "c" * 64): True}
    assert_not_duplicate(project, "d" * 64, lambda pid, sha: seen.get((pid, sha), False))
