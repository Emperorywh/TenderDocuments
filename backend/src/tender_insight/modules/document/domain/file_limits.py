"""可配置文件上传限额策略（C-027）。

将部署限额（单文件字节数、项目文件数、项目总字节数）封装为强类型值对象，全部来自
配置（A-013），领域代码不含魔法常量（SPEC.md 第 3.2、17 节）。修改配置即可改变限制。
"""

from __future__ import annotations

from dataclasses import dataclass

from tender_insight.modules.document.domain.exceptions import FileLimitExceededError


@dataclass(frozen=True)
class FileLimits:
    """部署文件限额。由配置构造，不在领域层硬编码。"""

    max_file_bytes: int
    max_files_per_project: int
    max_project_bytes: int

    @classmethod
    def from_settings(cls, settings: object) -> FileLimits:
        """从强类型配置（A-013 Settings 或同类对象）构造，领域不硬编码限额。"""
        return cls(
            max_file_bytes=int(settings.max_file_bytes),
            max_files_per_project=int(settings.max_files_per_project),
            max_project_bytes=int(settings.max_project_bytes),
        )

    def assert_file_size(self, size_bytes: int) -> None:
        if size_bytes > self.max_file_bytes:
            raise FileLimitExceededError(
                f"单文件大小 {size_bytes} 超过上限 {self.max_file_bytes}"
            )

    def assert_file_count(self, current_count: int) -> None:
        """在新增一个文件前校验：current_count 为当前已有数。"""
        if current_count >= self.max_files_per_project:
            raise FileLimitExceededError(
                f"项目文件数 {current_count} 达到上限 {self.max_files_per_project}"
            )

    def assert_project_bytes(self, current_bytes: int, adding_bytes: int) -> None:
        total = current_bytes + adding_bytes
        if total > self.max_project_bytes:
            raise FileLimitExceededError(
                f"项目总字节 {total} 将超过上限 {self.max_project_bytes}"
            )
