"""创建上传会话 API 契约测试（C-008 独立验证）。

验证契约不含身份字段，且成功/失败响应符合预期。
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tender_insight.bootstrap.db import get_object_storage, get_session
from tender_insight.main import create_app
from tender_insight.modules.document.api import create_router as document_router
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.shared.errors import add_problem_exception_handler
from tender_insight.shared.identifiers import Uuid


def _client(session: Session, storage: MagicMock) -> TestClient:
    app = create_app()
    app.include_router(document_router())
    add_problem_exception_handler(app)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_object_storage] = lambda: storage
    return TestClient(app)


def _storage() -> MagicMock:
    storage = MagicMock()
    storage.presigned_put_url.return_value = "https://minio.local/upload"
    return storage


def _seed_project(session: Session) -> str:
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
    return str(pid)


def test_create_upload_session_success(db_session: Session) -> None:
    """合法请求返回 201 与上传信息，无身份字段。"""
    pid = _seed_project(db_session)
    with _client(db_session, _storage()) as client:
        response = client.post(
            "/api/v1/upload-sessions",
            json={
                "project_id": pid,
                "declared_filename": "tender.pdf",
                "declared_size_bytes": 2048,
                "declared_mime": "application/pdf",
            },
        )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"session_id", "object_key", "upload_url", "expires_at", "method"}
    assert body["object_key"].startswith("quarantine/")
    # 无身份字段。
    forbidden = {"user_id", "operator", "created_by", "organization_id"}
    assert not (forbidden & set(body))


def test_missing_field_returns_422(db_session: Session) -> None:
    pid = _seed_project(db_session)
    with _client(db_session, _storage()) as client:
        response = client.post(
            "/api/v1/upload-sessions",
            json={"project_id": pid, "declared_filename": "x.pdf", "declared_mime": "application/pdf"},
        )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_unknown_project_returns_404(db_session: Session) -> None:
    with _client(db_session, _storage()) as client:
        response = client.post(
            "/api/v1/upload-sessions",
            json={
                "project_id": str(Uuid.new()),
                "declared_filename": "x.pdf",
                "declared_size_bytes": 10,
                "declared_mime": "application/pdf",
            },
        )
    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"
