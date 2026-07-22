"""上传完成接入用例测试（C-017 独立验证）。

验证校验通过后正式创建 DocumentVersion，任一校验失败时业务表与对象区无残留。
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from tender_insight.modules.document.application import (
    ObjectCategory,
)
from tender_insight.modules.document.application.complete_upload import (
    CompleteUploadCommand,
    CompleteUploadUseCase,
)
from tender_insight.modules.document.application.create_upload_session import (
    CreateUploadSessionCommand,
    CreateUploadSessionUseCase,
)
from tender_insight.modules.document.domain.exceptions import (
    DuplicateFileError,
    FileTypeMismatchError,
)
from tender_insight.modules.document.infrastructure.document_repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentVersionRepository,
)
from tender_insight.modules.document.infrastructure.models import (
    DocumentModel,
    DocumentVersionModel,
)
from tender_insight.modules.document.infrastructure.upload_session_repository import (
    SqlAlchemyUploadSessionRepository,
)
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid

_PDF = b"%PDF-1.7\nbody\n%%EOF"
_DOCX_VALID = b"PK\x03\x04" + b"\x00" * 30  # 简化 ZIP 魔数（仅用于类型识别）


def _clock():
    class _Clock:
        def now(self) -> datetime:
            return datetime(2026, 7, 23, tzinfo=UTC)

    return _Clock()


def _storage(data: bytes, *, existing: bool = True) -> MagicMock:
    storage = MagicMock()
    storage.exists.return_value = existing
    storage.size.return_value = len(data)
    storage.get.return_value = data
    storage.move.return_value = None
    storage.presigned_put_url.return_value = "https://minio.local/upload"
    return storage


def _seed(session: Session) -> tuple[Uuid, Uuid]:
    """建项目并创建一个上传会话，返回 (project_id, session_id)。"""
    pid = Uuid.new()
    session.add(
        ProjectModel(
            id=pid.value,
            name="p",
            region="成都",
            industry="房建",
            project_type="施工",
            lifecycle_state="ACTIVE",
            version=1,
        )
    )
    session.commit()
    use_case = CreateUploadSessionUseCase(
        repository=SqlAlchemyUploadSessionRepository(session),
        session=session,
        object_storage=_storage(_PDF),
        project_exists=lambda i: True,
        max_file_bytes=10 * 1024 * 1024,
        clock=_clock(),
    )
    info = use_case.execute(
        CreateUploadSessionCommand(
            project_id=str(pid),
            declared_filename="tender.pdf",
            declared_size_bytes=len(_PDF),
            declared_mime="application/pdf",
        )
    )
    # info.object_key 是 quarantine/<uuid>；返回的 session_id
    return pid, Uuid.from_str(info.session_id)


def _use_case(session: Session, storage: MagicMock) -> CompleteUploadUseCase:
    return CompleteUploadUseCase(
        upload_session_repository=SqlAlchemyUploadSessionRepository(session),
        document_repository=SqlAlchemyDocumentRepository(session),
        version_repository=SqlAlchemyDocumentVersionRepository(session),
        object_storage=storage,
        session=session,
        max_uncompressed_bytes=10 * 1024 * 1024,
        max_compression_ratio=1000.0,
        clock=_clock(),
    )


def test_success_creates_version_and_moves_object(db_session: Session) -> None:
    _, session_id = _seed(db_session)
    storage = _storage(_PDF)
    result = _use_case(db_session, storage).execute(CompleteUploadCommand(session_id=str(session_id)))

    assert result.sha256
    assert result.version_number == 1
    # Document 与 Version 已创建。
    assert db_session.query(DocumentModel).count() == 1
    assert db_session.query(DocumentVersionModel).count() == 1
    version = db_session.query(DocumentVersionModel).one()
    assert version.status == "STORED"
    assert version.original_object_key.startswith("original/")
    # 对象已从 quarantine 移动。
    storage.move.assert_called_once()
    args = storage.move.call_args[0]
    assert args[0].category == ObjectCategory.QUARANTINE
    assert args[1].category == ObjectCategory.ORIGINAL


def test_file_type_mismatch_leaves_no_residue(db_session: Session) -> None:
    """校验失败时业务表与对象区无残留。"""
    _, session_id = _seed(db_session)
    # 内容是 PDF，但会话声明为 DOCX（_seed 用 PDF，这里改声明）。
    # 重新构造一个声明为 docx 的会话。
    pid = db_session.query(ProjectModel).one().id
    create = CreateUploadSessionUseCase(
        repository=SqlAlchemyUploadSessionRepository(db_session),
        session=db_session,
        object_storage=_storage(_DOCX_VALID),
        project_exists=lambda i: True,
        max_file_bytes=10 * 1024 * 1024,
        clock=_clock(),
    )
    info = create.execute(
        CreateUploadSessionCommand(
            project_id=str(pid),
            declared_filename="t.docx",
            declared_size_bytes=len(_PDF),  # 实际内容是 PDF
            declared_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    )
    sid = Uuid.from_str(info.session_id)
    # storage 返回 PDF 字节，但会话声明 DOCX → 类型不一致。
    storage = _storage(_PDF)
    with pytest.raises(FileTypeMismatchError):
        _use_case(db_session, storage).execute(CompleteUploadCommand(session_id=str(sid)))

    # 无 Document/Version，对象未移动。
    assert db_session.query(DocumentModel).count() == 0
    assert db_session.query(DocumentVersionModel).count() == 0
    storage.move.assert_not_called()


def test_duplicate_hash_rejected(db_session: Session) -> None:
    """同项目同哈希不重复创建版本。"""
    _, first_session = _seed(db_session)
    storage = _storage(_PDF)
    _use_case(db_session, storage).execute(CompleteUploadCommand(session_id=str(first_session)))

    # 第二个相同内容会话。
    pid = db_session.query(ProjectModel).one().id
    create = CreateUploadSessionUseCase(
        repository=SqlAlchemyUploadSessionRepository(db_session),
        session=db_session,
        object_storage=_storage(_PDF),
        project_exists=lambda i: True,
        max_file_bytes=10 * 1024 * 1024,
        clock=_clock(),
    )
    info2 = create.execute(
        CreateUploadSessionCommand(
            project_id=str(pid),
            declared_filename="dup.pdf",
            declared_size_bytes=len(_PDF),
            declared_mime="application/pdf",
        )
    )
    storage2 = _storage(_PDF)
    with pytest.raises(DuplicateFileError):
        _use_case(db_session, storage2).execute(
            CompleteUploadCommand(session_id=info2.session_id)
        )
    # 仍只有一个版本。
    assert db_session.query(DocumentVersionModel).count() == 1


def test_unknown_session_not_found(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        _use_case(db_session, _storage(_PDF)).execute(
            CompleteUploadCommand(session_id=str(Uuid.new()))
        )
