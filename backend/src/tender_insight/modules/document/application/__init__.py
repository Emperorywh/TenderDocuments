"""document 模块应用层端口（C-001 起）。

定义 ObjectStorage 端口及对象键/分类等稳定类型。端口刻意保持纯（仅标准库），
使 application/domain 不依赖 MinIO 或任何对象存储 SDK（PLAN.md 第 3.4 节
ObjectStorage 为关键替换边界）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from tender_insight.modules.document.domain.document import Document
from tender_insight.modules.document.domain.document_version import DocumentVersion
from tender_insight.modules.document.domain.upload_session import UploadSession
from tender_insight.shared.identifiers import Uuid


class SecurityScanResult(StrEnum):
    """安全扫描结果。"""

    CLEAN = "CLEAN"
    SUSPICIOUS = "SUSPICIOUS"


@dataclass(frozen=True)
class SecurityScanOutcome:
    """安全扫描结果详情。"""

    result: SecurityScanResult
    reason: str | None = None


class FileSecurityScanner(Protocol):
    """文件安全扫描端口（SPEC.md 第 11.1 节 quarantine 安全检查）。

    由基础设施实现（如 ClamAV/杀毒适配器）；领域层不依赖具体扫描器。
    """

    def scan(self, data: bytes, *, filename: str, mime: str) -> SecurityScanOutcome:
        """扫描文件字节，返回 CLEAN 或 SUSPICIOUS。"""
        ...


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

    def size(self, key: ObjectKey) -> int:
        """返回对象字节数；对象不存在时抛错。"""
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

    def add(self, upload_session: UploadSession) -> None:
        ...

    def get(self, session_id: Uuid) -> UploadSession | None:
        ...

    def save(self, upload_session: UploadSession) -> None:
        ...


class DocumentRepository(Protocol):
    """逻辑文件仓储端口。"""

    def add(self, document: Document) -> None:
        ...

    def get(self, document_id: Uuid) -> Document | None:
        ...


class DocumentVersionRepository(Protocol):
    """文件版本仓储端口。"""

    def add(self, version: DocumentVersion) -> None:
        ...

    def next_version_number(self, document_id: Uuid) -> int:
        """返回该逻辑文件下一个版本号（从 1 起）。"""
        ...

    def exists_by_sha256_in_project(self, project_id: Uuid, sha256: str) -> bool:
        """项目内是否已存在同哈希版本（重复检测，C-018）。"""
        ...
