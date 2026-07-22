"""同项目哈希重复领域策略（C-018）。

SPEC.md 第 6.4、11.1 节：同项目内完全重复（相同 SHA-256）的文件不得重复创建
有效版本或重复分析。本策略以纯函数表达该规则，供上传完成（C-017）等场景复用。
"""

from __future__ import annotations

from collections.abc import Callable

from tender_insight.modules.document.domain.exceptions import DuplicateFileError
from tender_insight.shared.identifiers import Uuid


def assert_not_duplicate(
    project_id: Uuid,
    sha256: str,
    exists_in_project: Callable[[Uuid, str], bool],
) -> None:
    """若项目内已存在相同哈希的有效版本，抛 DuplicateFileError。"""
    if exists_in_project(project_id, sha256):
        raise DuplicateFileError(
            f"同项目内已存在相同哈希文件：sha256={sha256}"
        )
