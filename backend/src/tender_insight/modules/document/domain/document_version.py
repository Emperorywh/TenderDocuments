"""DocumentVersion 领域实体（C-015）。

不可变文件版本：核心原始元数据（original_object_key/sha256/size_bytes/mime/
version_number/document_id）一经创建只读，仅 status 与处理态字段可演进
（SPEC.md 第 5.2、6.4 节）。状态转换经集中校验，非法转换被拒绝。

通过私有化核心字段写入（仅构造时赋值）实现不可变；公开方法只变更状态/处理态。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.state_transitions import validate_transition
from tender_insight.shared.states import DocumentVersionStatus


@dataclass
class DocumentVersion:
    """不可变文件版本聚合。

    核心字段以只读 property 暴露，避免被外部覆盖；状态机方法仅改 status 与处理态。
    """

    _id: Uuid
    _document_id: Uuid
    _version_number: int
    _original_object_key: str
    _sha256: str
    _size_bytes: int
    _mime: str
    status: DocumentVersionStatus
    canonical_object_key: str | None = None
    page_count: int | None = None
    published_date: datetime | None = None
    effect_order: int | None = None

    # ---- 只读核心字段 ----
    @property
    def id(self) -> Uuid:
        return self._id

    @property
    def document_id(self) -> Uuid:
        return self._document_id

    @property
    def version_number(self) -> int:
        return self._version_number

    @property
    def original_object_key(self) -> str:
        return self._original_object_key

    @property
    def sha256(self) -> str:
        return self._sha256

    @property
    def size_bytes(self) -> int:
        return self._size_bytes

    @property
    def mime(self) -> str:
        return self._mime

    @classmethod
    def create(
        cls,
        *,
        version_id: Uuid,
        document_id: Uuid,
        version_number: int,
        original_object_key: str,
        sha256: str,
        size_bytes: int,
        mime: str,
    ) -> DocumentVersion:
        """创建新版本（STORED 前的初始状态由接入用例决定，此处默认 UPLOADING）。"""
        if version_number < 1:
            raise ValueError("版本号必须 >= 1")
        if not sha256.strip():
            raise ValueError("SHA-256 不能为空")
        return cls(
            _id=version_id,
            _document_id=document_id,
            _version_number=version_number,
            _original_object_key=original_object_key,
            _sha256=sha256,
            _size_bytes=size_bytes,
            _mime=mime,
            status=DocumentVersionStatus.UPLOADING,
        )

    # ---- 状态机（仅改 status 与处理态，不动核心字段）----
    def _transition(self, target: DocumentVersionStatus) -> None:
        validate_transition(DocumentVersionStatus, self.status, target)
        self.status = target

    def mark_stored(self) -> None:
        self._transition(DocumentVersionStatus.STORED)

    def mark_validating(self) -> None:
        self._transition(DocumentVersionStatus.VALIDATING)

    def mark_ready(
        self,
        *,
        canonical_object_key: str | None = None,
        page_count: int | None = None,
    ) -> None:
        self._transition(DocumentVersionStatus.READY)
        # canonical/page_count 是处理态补充，不是对原始元数据的覆盖。
        if canonical_object_key is not None:
            self.canonical_object_key = canonical_object_key
        if page_count is not None:
            self.page_count = page_count

    def reject(self) -> None:
        self._transition(DocumentVersionStatus.REJECTED)
