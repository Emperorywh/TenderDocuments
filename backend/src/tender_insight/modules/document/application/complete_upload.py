"""上传完成接入用例（C-017）。

把已上传对象正式接入为不可变 DocumentVersion：串联对象校验、文件类型/完整性/
压缩校验与 SHA-256，校验全部通过后才移动对象到 original 分区并创建 Document 与
DocumentVersion。任一校验失败时业务表与正式对象区均无残留（校验先于任何变更）。
"""

from __future__ import annotations

import contextlib

from pydantic import BaseModel

from tender_insight.modules.document.application import (
    DocumentRepository,
    DocumentVersionRepository,
    ObjectCategory,
    ObjectKey,
    ObjectStorage,
    UploadSessionRepository,
)
from tender_insight.modules.document.application.upload_verification import (
    verify_uploaded_object,
)
from tender_insight.modules.document.domain.compression import validate_compression
from tender_insight.modules.document.domain.document import Document
from tender_insight.modules.document.domain.document_types import DocumentBusinessType
from tender_insight.modules.document.domain.document_version import DocumentVersion
from tender_insight.modules.document.domain.file_integrity import validate_file_integrity
from tender_insight.modules.document.domain.file_type import validate_file_type
from tender_insight.modules.document.domain.hashing import iter_chunks, sha256_streaming
from tender_insight.shared.business_time import BusinessInstant, Clock
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid


class CompleteUploadCommand(BaseModel):
    session_id: str


class CompleteUploadResult(BaseModel):
    document_id: str
    version_id: str
    version_number: int
    sha256: str


def _parse_object_key(object_key: str) -> ObjectKey:
    parts = object_key.split("/", 1)
    return ObjectKey(category=ObjectCategory(parts[0]), key=parts[1])


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1] if "." in filename else ""


class CompleteUploadUseCase:
    def __init__(
        self,
        *,
        upload_session_repository: UploadSessionRepository,
        document_repository: DocumentRepository,
        version_repository: DocumentVersionRepository,
        object_storage: ObjectStorage,
        session,
        max_uncompressed_bytes: int,
        max_compression_ratio: float,
        clock: Clock | None = None,
    ) -> None:
        self._uploads = upload_session_repository
        self._documents = document_repository
        self._versions = version_repository
        self._storage = object_storage
        self._session = session
        self._max_uncompressed = max_uncompressed_bytes
        self._max_ratio = max_compression_ratio
        self._clock = clock

    def execute(self, command: CompleteUploadCommand) -> CompleteUploadResult:
        session_id = Uuid.from_str(command.session_id)
        upload = self._uploads.get(session_id)
        if upload is None:
            raise NotFoundError(f"上传会话不存在：{command.session_id}")
        now = BusinessInstant.now(clock=self._clock).value
        if not upload.can_complete(now):
            raise PermissionError("上传会话不可完成（已过期或状态非法）")

        # ---- 校验阶段：任何失败都不产生业务变更/对象移动 ----
        actual_size = verify_uploaded_object(
            self._storage, upload.object_key, upload.declared_size_bytes
        )
        src_key = _parse_object_key(upload.object_key)
        data = self._storage.get(src_key)
        validate_file_type(
            data,
            declared_mime=upload.declared_mime,
            declared_extension=_extension(upload.declared_filename),
        )
        validate_file_integrity(data)
        validate_compression(
            data,
            max_uncompressed_bytes=self._max_uncompressed,
            max_ratio=self._max_ratio,
        )
        digest = sha256_streaming(iter_chunks(data))
        # 同项目哈希重复策略（C-018）。
        from tender_insight.modules.document.domain.duplicate_policy import assert_not_duplicate

        assert_not_duplicate(
            upload.project_id,
            digest,
            self._versions.exists_by_sha256_in_project,
        )

        # ---- 变更阶段：移动对象 → 创建 Document + Version → 标记会话完成 ----
        dest_key = ObjectKey(category=ObjectCategory.ORIGINAL, key=str(Uuid.new()))
        self._storage.move(src_key, dest_key)
        try:
            document = Document(
                id=Uuid.new(),
                project_id=upload.project_id,
                business_type=DocumentBusinessType.OTHER,  # 业务类型在 C-021 由用户确认
                name=upload.declared_filename,
            )
            self._documents.add(document)

            version = DocumentVersion.create(
                version_id=Uuid.new(),
                document_id=document.id,
                version_number=self._versions.next_version_number(document.id),
                original_object_key=dest_key.as_path(),
                sha256=digest,
                size_bytes=actual_size,
                mime=upload.declared_mime,
            )
            version.mark_stored()
            self._versions.add(version)

            upload.complete(now=now)
            self._uploads.save(upload)
            self._session.commit()
        except Exception:
            self._session.rollback()
            # 失败时尽力把对象移回隔离区，避免 original 残留孤儿。
            self._safe_move_back(dest_key, src_key)
            raise

        return CompleteUploadResult(
            document_id=str(document.id),
            version_id=str(version.id),
            version_number=version.version_number,
            sha256=digest,
        )

    def _safe_move_back(self, dest_key: ObjectKey, src_key: ObjectKey) -> None:
        # 清理失败不掩盖原始异常。
        with contextlib.suppress(Exception):
            self._storage.move(dest_key, src_key)
