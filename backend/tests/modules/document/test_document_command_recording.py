"""文件关键操作记录集成测试（C-030 独立验证）。

验证上传、查看、下载、关系变更与元数据确认等文件命令恰好产生一条操作记录
（成功同事务、失败独立事务持久化），复用 B-017 record_command_outcome 模式。
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session, sessionmaker

from tender_insight.modules.document.application.complete_upload import (
    CompleteUploadCommand,
    CompleteUploadUseCase,
)
from tender_insight.modules.document.application.confirm_document_type import (
    ConfirmDocumentTypeCommand,
    ConfirmDocumentTypeUseCase,
)
from tender_insight.modules.document.application.confirm_published_date import (
    ConfirmPublishedDateCommand,
    ConfirmPublishedDateUseCase,
)
from tender_insight.modules.document.application.create_document_relation import (
    CreateDocumentRelationCommand,
    CreateDocumentRelationUseCase,
)
from tender_insight.modules.document.application.create_original_file_access_url import (
    CreateOriginalFileAccessUrlUseCase,
)
from tender_insight.modules.document.application.create_upload_session import (
    CreateUploadSessionCommand,
    CreateUploadSessionUseCase,
)
from tender_insight.modules.document.application.list_documents import (
    ListDocumentsUseCase,
)
from tender_insight.modules.document.domain.document import Document
from tender_insight.modules.document.domain.document_types import (
    DocumentBusinessType,
    DocumentRelationType,
)
from tender_insight.modules.document.domain.document_version import DocumentVersion
from tender_insight.modules.document.domain.exceptions import FileTypeMismatchError
from tender_insight.modules.document.infrastructure.document_relation_repository import (
    SqlAlchemyDocumentRelationRepository,
)
from tender_insight.modules.document.infrastructure.document_repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentVersionRepository,
)
from tender_insight.modules.document.infrastructure.models import DocumentModel
from tender_insight.modules.document.infrastructure.upload_session_repository import (
    SqlAlchemyUploadSessionRepository,
)
from tender_insight.modules.operation_log.infrastructure.models import OperationLogModel
from tender_insight.modules.operation_log.infrastructure.recorder import (
    SqlAlchemyOperationRecorder,
)
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.pagination import PageRequest

_PDF = b"%PDF-1.7\nbody\n%%EOF"


def _open_recorder(session: Session) -> SqlAlchemyOperationRecorder:
    return SqlAlchemyOperationRecorder(session)


def _recording_kwargs(session_factory: sessionmaker[Session]) -> dict:
    return {"session_factory": session_factory, "open_recorder": _open_recorder}


def _seed_project(session: Session) -> Uuid:
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
    return pid


def _storage(data: bytes) -> MagicMock:
    storage = MagicMock()
    storage.exists.return_value = True
    storage.size.return_value = len(data)
    storage.get.return_value = data
    storage.move.return_value = None
    storage.presigned_put_url.return_value = "https://minio.local/upload"
    storage.presigned_get_url.return_value = "https://minio.local/download"
    return storage


def _create_upload_session(
    session: Session, session_factory, pid: Uuid, storage: MagicMock
) -> Uuid:
    """经记录用例创建一个上传会话，返回会话 ID。"""
    info = CreateUploadSessionUseCase(
        repository=SqlAlchemyUploadSessionRepository(session),
        session=session,
        object_storage=storage,
        project_exists=lambda i: True,
        max_file_bytes=10 * 1024 * 1024,
        **_recording_kwargs(session_factory),
    ).execute(
        CreateUploadSessionCommand(
            project_id=str(pid),
            declared_filename="tender.pdf",
            declared_size_bytes=len(_PDF),
            declared_mime="application/pdf",
        )
    )
    return Uuid.from_str(info.session_id)


def test_upload_create_records_one_success(
    db_session: Session, session_factory
) -> None:
    """上传发起恰好产生一条 document.upload.create 成功记录。"""
    pid = _seed_project(db_session)
    storage = _storage(_PDF)
    _create_upload_session(db_session, session_factory, pid, storage)

    rows = [r for r in db_session.query(OperationLogModel).all() if r.action == "document.upload.create"]
    assert len(rows) == 1
    assert rows[0].result == "success"
    assert rows[0].resource_type == "project"
    assert rows[0].resource_id == str(pid)


def test_upload_complete_records_one_success(
    db_session: Session, session_factory
) -> None:
    """上传完成恰好产生一条 document.upload.complete 成功记录。"""
    pid = _seed_project(db_session)
    storage = _storage(_PDF)
    sid = _create_upload_session(db_session, session_factory, pid, storage)

    CompleteUploadUseCase(
        upload_session_repository=SqlAlchemyUploadSessionRepository(db_session),
        document_repository=SqlAlchemyDocumentRepository(db_session),
        version_repository=SqlAlchemyDocumentVersionRepository(db_session),
        object_storage=_storage(_PDF),
        session=db_session,
        max_uncompressed_bytes=10 * 1024 * 1024,
        max_compression_ratio=1000.0,
        **_recording_kwargs(session_factory),
    ).execute(CompleteUploadCommand(session_id=str(sid)))

    rows = [r for r in db_session.query(OperationLogModel).all() if r.action == "document.upload.complete"]
    assert len(rows) == 1
    assert rows[0].result == "success"
    assert rows[0].resource_type == "upload_session"
    assert rows[0].resource_id == str(sid)


def test_upload_complete_failure_records_failure(
    db_session: Session, session_factory
) -> None:
    """上传完成校验失败产生一条 failure 记录（独立事务持久化）。"""
    pid = _seed_project(db_session)
    storage = _storage(_PDF)
    sid = _create_upload_session(db_session, session_factory, pid, storage)

    # 内容非法（非 PDF 魔数），但会话声明 PDF → 类型不一致。
    bad = _storage(b"XXXXX")
    # 让大小校验通过（声明大小为 PDF 长度），逼到类型校验失败。
    bad.size.return_value = len(_PDF)
    with pytest.raises(FileTypeMismatchError):
        CompleteUploadUseCase(
            upload_session_repository=SqlAlchemyUploadSessionRepository(db_session),
            document_repository=SqlAlchemyDocumentRepository(db_session),
            version_repository=SqlAlchemyDocumentVersionRepository(db_session),
            object_storage=bad,
            session=db_session,
            max_uncompressed_bytes=10 * 1024 * 1024,
            max_compression_ratio=1000.0,
            **_recording_kwargs(session_factory),
        ).execute(CompleteUploadCommand(session_id=str(sid)))

    rows = [r for r in db_session.query(OperationLogModel).all() if r.action == "document.upload.complete"]
    assert len(rows) == 1
    assert rows[0].result == "failure"
    assert rows[0].error_code == "FILE_TYPE_MISMATCH"


def _seed_document(session: Session, pid: Uuid) -> tuple[Uuid, Uuid]:
    doc = Document(
        id=Uuid.new(), project_id=pid, business_type=DocumentBusinessType.OTHER, name="t.pdf"
    )
    SqlAlchemyDocumentRepository(session).add(doc)
    session.commit()
    version = DocumentVersion.create(
        version_id=Uuid.new(),
        document_id=doc.id,
        version_number=1,
        original_object_key="original/abc",
        sha256="a" * 64,
        size_bytes=10,
        mime="application/pdf",
    )
    SqlAlchemyDocumentVersionRepository(session).add(version)
    session.commit()
    return doc.id, version.id


def test_confirm_type_records_one_success(db_session: Session, session_factory) -> None:
    pid = _seed_project(db_session)
    doc_id, _ = _seed_document(db_session, pid)
    ConfirmDocumentTypeUseCase(
        repository=SqlAlchemyDocumentRepository(db_session),
        session=db_session,
        **_recording_kwargs(session_factory),
    ).execute(
        ConfirmDocumentTypeCommand(document_id=str(doc_id), business_type=DocumentBusinessType.TENDER_DOC)
    )
    rows = [r for r in db_session.query(OperationLogModel).all() if r.action == "document.confirm_type"]
    assert len(rows) == 1
    assert rows[0].result == "success"


def test_confirm_published_date_records_one_success(
    db_session: Session, session_factory
) -> None:
    pid = _seed_project(db_session)
    _, version_id = _seed_document(db_session, pid)
    ConfirmPublishedDateUseCase(
        repository=SqlAlchemyDocumentVersionRepository(db_session),
        session=db_session,
        **_recording_kwargs(session_factory),
    ).execute(
        ConfirmPublishedDateCommand(
            version_id=str(version_id), published_at=datetime(2026, 7, 23, tzinfo=UTC)
        )
    )
    rows = [r for r in db_session.query(OperationLogModel).all() if r.action == "document.confirm_published_date"]
    assert len(rows) == 1
    assert rows[0].result == "success"


def test_unknown_document_confirm_records_failure(
    db_session: Session, session_factory
) -> None:
    """未知文件确认类型产生一条 failure（NOT_FOUND）记录。"""
    with pytest.raises(NotFoundError):
        ConfirmDocumentTypeUseCase(
            repository=SqlAlchemyDocumentRepository(db_session),
            session=db_session,
            **_recording_kwargs(session_factory),
        ).execute(
            ConfirmDocumentTypeCommand(
                document_id=str(Uuid.new()), business_type=DocumentBusinessType.TENDER_DOC
            )
        )
    rows = db_session.query(OperationLogModel).all()
    assert len(rows) == 1
    assert rows[0].result == "failure"
    assert rows[0].error_code == "NOT_FOUND"


def test_relation_create_records_one_success(
    db_session: Session, session_factory
) -> None:
    """关系变更恰好产生一条 document.relation.create 成功记录。"""
    pid = _seed_project(db_session)
    src, _ = _seed_document(db_session, pid)
    tgt, _ = _seed_document(db_session, pid)
    CreateDocumentRelationUseCase(
        document_repository=SqlAlchemyDocumentRepository(db_session),
        relation_repository=SqlAlchemyDocumentRelationRepository(db_session),
        session=db_session,
        **_recording_kwargs(session_factory),
    ).execute(
        CreateDocumentRelationCommand(
            project_id=str(pid),
            source_document_id=str(src),
            target_document_id=str(tgt),
            relation_type=DocumentRelationType.SUPPLEMENTS,
        )
    )
    rows = [r for r in db_session.query(OperationLogModel).all() if r.action == "document.relation.create"]
    assert len(rows) == 1
    assert rows[0].result == "success"


def test_download_records_one_success(db_session: Session, session_factory) -> None:
    """下载签发恰好产生一条 document.download 成功记录。"""
    pid = _seed_project(db_session)
    _, version_id = _seed_document(db_session, pid)
    CreateOriginalFileAccessUrlUseCase(
        version_repository=SqlAlchemyDocumentVersionRepository(db_session),
        object_storage=_storage(_PDF),
        ttl_seconds=900,
        session=db_session,
        **_recording_kwargs(session_factory),
    ).execute(version_id)
    rows = [r for r in db_session.query(OperationLogModel).all() if r.action == "document.download"]
    assert len(rows) == 1
    assert rows[0].result == "success"
    assert rows[0].resource_id == str(version_id)


def test_view_records_one_success(db_session: Session, session_factory) -> None:
    """查看文件列表恰好产生一条 document.view 成功记录。"""
    pid = _seed_project(db_session)
    _seed_document(db_session, pid)
    ListDocumentsUseCase(
        session=db_session,
        project_id=pid,
        page_request=PageRequest(page=1, page_size=20),
        **_recording_kwargs(session_factory),
    ).execute()
    rows = [r for r in db_session.query(OperationLogModel).all() if r.action == "document.view"]
    assert len(rows) == 1
    assert rows[0].result == "success"
    assert rows[0].resource_type == "project"


def test_each_action_distinct(db_session: Session, session_factory) -> None:
    """各文件关键操作动作名称互不相同（上传/查看/下载/关系/确认）。"""
    pid = _seed_project(db_session)
    storage = _storage(_PDF)
    sid = _create_upload_session(db_session, session_factory, pid, storage)

    CompleteUploadUseCase(
        upload_session_repository=SqlAlchemyUploadSessionRepository(db_session),
        document_repository=SqlAlchemyDocumentRepository(db_session),
        version_repository=SqlAlchemyDocumentVersionRepository(db_session),
        object_storage=_storage(_PDF),
        session=db_session,
        max_uncompressed_bytes=10 * 1024 * 1024,
        max_compression_ratio=1000.0,
        **_recording_kwargs(session_factory),
    ).execute(CompleteUploadCommand(session_id=str(sid)))

    # 上传完成创建一个 Document+Version，复用做确认/下载/查看。
    doc = db_session.query(DocumentModel).one()

    # 取首个版本 ID。
    from tender_insight.modules.document.infrastructure.models import DocumentVersionModel

    version_id = db_session.query(DocumentVersionModel).first().id

    ConfirmDocumentTypeUseCase(
        repository=SqlAlchemyDocumentRepository(db_session),
        session=db_session,
        **_recording_kwargs(session_factory),
    ).execute(
        ConfirmDocumentTypeCommand(
            document_id=str(doc.id), business_type=DocumentBusinessType.TENDER_DOC
        )
    )
    CreateOriginalFileAccessUrlUseCase(
        version_repository=SqlAlchemyDocumentVersionRepository(db_session),
        object_storage=_storage(_PDF),
        ttl_seconds=900,
        session=db_session,
        **_recording_kwargs(session_factory),
    ).execute(Uuid(version_id))
    ListDocumentsUseCase(
        session=db_session,
        project_id=pid,
        page_request=PageRequest(page=1, page_size=20),
        **_recording_kwargs(session_factory),
    ).execute()

    actions = {r.action for r in db_session.query(OperationLogModel).all()}
    assert "document.upload.create" in actions
    assert "document.upload.complete" in actions
    assert "document.confirm_type" in actions
    assert "document.download" in actions
    assert "document.view" in actions
