"""document 模块应用层端口（C-001 起）。

定义 ObjectStorage 端口及对象键/分类等稳定类型。端口刻意保持纯（仅标准库），
使 application/domain 不依赖 MinIO 或任何对象存储 SDK（PLAN.md 第 3.4 节
ObjectStorage 为关键替换边界）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from tender_insight.modules.document.domain.upload_session import UploadSession
from tender_insight.shared.identifiers import Uuid


class ObjectCategory(StrEnum):
    """对象存储分区（SPEC.md 第 6.4 节）。

    对象键不得包含可猜测的原始文件名路径，故以分类 + 不可猜测键组织。
    """

    ORIGINAL = "original"
    CANONICAL = "canonical"
    PAGES = "pages"
    ARTIFACTS = "artifacts"
    REPORTS = "reports"
    QUARANTINE = "quarantine"


@dataclass(frozen=True)
class ObjectKey:
    """对象键：分类 + 不可猜测的键字符串。

    key 不含原始文件名，避免可猜测路径；由系统生成（如 UUID 组合）。
    """

    category: ObjectCategory
    key: str

    def as_path(self) -> str:
        """返回存储内路径：分类/键。"""
        return f"{self.category.value}/{self.key}"


class ObjectStorage(Protocol):
    """对象存储端口：写入、读取、移动、删除与短期授权地址。

    对象默认私有；读取经 presigned_get_url 取短期授权地址，不直接公开。
    """

    def put(self, key: ObjectKey, data: bytes, *, content_type: str) -> None:
        """写入对象。"""
        ...

    def get(self, key: ObjectKey) -> bytes:
        """读取对象全部字节（用于服务端处理，不对外）。"""
        ...

    def exists(self, key: ObjectKey) -> bool:
        """对象是否存在。"""
        ...

    def delete(self, key: ObjectKey) -> None:
        """删除对象（幂等）。"""
        ...

    def move(self, source: ObjectKey, destination: ObjectKey) -> None:
        """移动对象；移动后源键失效。"""
        ...

    def presigned_get_url(self, key: ObjectKey, *, expires_in_seconds: int) -> str:
        """生成短期授权读取地址；到期失效。"""
        ...

    def presigned_put_url(self, key: ObjectKey, *, expires_in_seconds: int) -> str:
        """生成短期授权上传地址（客户端直传）；到期失效。"""
        ...


class UploadSessionRepository(Protocol):
    """上传会话仓储端口。"""

    def add(self, session: UploadSession) -> None:
        ...

    def get(self, session_id: Uuid) -> UploadSession | None:
        ...
