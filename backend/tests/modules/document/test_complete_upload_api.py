"""上传完成确认 API 契约测试（C-034 独立验证）。

验证校验成功才返回 DocumentVersion，校验失败时无业务残留（无 Document/Version）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tender_insight.bootstrap.db import get_object_storage, get_session
from tender_insight.main import create_app
from tender_insight.modules.document.api import create_router as document_router
from tender_insight.modules.document.domain.upload_session import UploadSession
from tender_insight.modules.document.infrastructure.models import (
    DocumentModel,
    DocumentVersionModel,
)
from tender_insight.modules.document.infrastructure.upload_session_repository import (
    SqlAlchemyUploadSessionRepository,
)
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.shared.errors import add_problem_exception_handler
from tender_insight.shared.identifiers import Uuid

# 合法 PDF 字节（含魔数与尾标记，通过类型与完整性校验）。
_PDF = b"%PDF-1.7\nbody\n%%EOF"


def _client(session: Session, storage: MagicMock) -> TestClient:
    app = create_app()
    app.include_router(document_router())
    add_problem_exception_handler(app)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_object_storage] = lambda: storage
    return TestClient(app)


def _storage(data: bytes) -> MagicMock:
    """对象存储 mock：exists/size/get/move 行为符合完整接入需要。"""
    storage = MagicMock()
    storage.exists.return_value = True
    storage.size.return_value = len(data)
    storage.get.return_value = data
    storage.move.return_value = None
    return storage


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


def _seed_session(
    session: Session,
    project_id: Uuid,
    *,
    declared_mime: str,
    declared_filename: str,
    size: int,
) -> Uuid:
    """直接经仓储创建一个 PENDING 上传会话，返回会话 ID。

    时间基于真实时钟（用例内 BusinessInstant.now 不注入时钟），故以当前时刻
    向后延一小时，保证会话在接入用例执行时仍处于有效期内。
    """
    now = datetime.now(UTC)
    upload = UploadSession.create(
        project_id=project_id,
        declared_filename=declared_filename,
        declared_size_bytes=size,
        declared_mime=declared_mime,
        object_key="quarantine/abc",
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    SqlAlchemyUploadSessionRepository(session).add(upload)
    session.commit()
    return upload.id


def test_complete_upload_success(db_session: Session) -> None:
    """校验通过后正式创建 DocumentVersion，返回 201 与版本标识。"""
    pid = _seed_project(db_session)
    sid = _seed_session(
        db_session,
        pid,
        declared_mime="application/pdf",
        declared_filename="tender.pdf",
        size=len(_PDF),
    )
    with _client(db_session, _storage(_PDF)) as client:
        response = client.post(f"/api/v1/upload-sessions/{sid}/complete")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"document_id", "version_id", "version_number", "sha256"}
    assert body["version_number"] == 1
    assert body["sha256"]
    # 业务文件与版本均已创建。
    assert db_session.query(DocumentModel).count() == 1
    assert db_session.query(DocumentVersionModel).count() == 1
    # 响应无身份字段。
    assert not ({"user_id", "operator", "created_by", "organization_id"} & set(body))


def test_complete_upload_type_mismatch_no_residue(db_session: Session) -> None:
    """声明 PDF 但实际为非法内容：返回 400 且无业务残留。"""
    pid = _seed_project(db_session)
    # 声明 PDF，但 storage 返回不含 PDF 魔数与尾标记的字节。
    sid = _seed_session(
        db_session,
        pid,
        declared_mime="application/pdf",
        declared_filename="tender.pdf",
        size=5,
    )
    bad = b"XXXXX"  # 非 PDF 魔数
    with _client(db_session, _storage(bad)) as client:
        response = client.post(f"/api/v1/upload-sessions/{sid}/complete")

    assert response.status_code == 400
    assert response.json()["error_code"] == "FILE_TYPE_MISMATCH"
    # 无业务残留。
    assert db_session.query(DocumentModel).count() == 0
    assert db_session.query(DocumentVersionModel).count() == 0


def test_complete_unknown_session_returns_404(db_session: Session) -> None:
    _seed_project(db_session)
    with _client(db_session, _storage(_PDF)) as client:
        response = client.post(
            f"/api/v1/upload-sessions/{Uuid.new()}/complete"
        )
    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"
