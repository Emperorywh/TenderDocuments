"""文件元数据确认 API 契约测试（C-031 独立验证）。

验证类型与发布日期的成功与失败响应符合契约。
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tender_insight.bootstrap.db import get_object_storage, get_session
from tender_insight.main import create_app
from tender_insight.modules.document.api import create_router as document_router
from tender_insight.modules.document.domain.document import Document
from tender_insight.modules.document.domain.document_types import DocumentBusinessType
from tender_insight.modules.document.domain.document_version import DocumentVersion
from tender_insight.modules.document.infrastructure.document_repositories import (
    SqlAlchemyDocumentRepository,
    SqlAlchemyDocumentVersionRepository,
)
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.shared.errors import add_problem_exception_handler
from tender_insight.shared.identifiers import Uuid


def _client(session: Session) -> TestClient:
    app = create_app()
    app.include_router(document_router())
    add_problem_exception_handler(app)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_object_storage] = lambda: MagicMock()
    return TestClient(app)


def _seed(session: Session) -> tuple[Uuid, Uuid]:
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
    doc_repo = SqlAlchemyDocumentRepository(session)
    doc = Document(
        id=Uuid.new(),
        project_id=pid,
        business_type=DocumentBusinessType.OTHER,
        name="t.pdf",
    )
    doc_repo.add(doc)
    session.commit()
    ver_repo = SqlAlchemyDocumentVersionRepository(session)
    version = DocumentVersion.create(
        version_id=Uuid.new(),
        document_id=doc.id,
        version_number=1,
        original_object_key="original/abc",
        sha256="a" * 64,
        size_bytes=10,
        mime="application/pdf",
    )
    ver_repo.add(version)
    session.commit()
    return doc.id, version.id


def test_confirm_type_success(db_session: Session) -> None:
    doc_id, _ = _seed(db_session)
    with _client(db_session) as client:
        response = client.patch(
            f"/api/v1/documents/{doc_id}/type",
            json={"document_id": str(doc_id), "business_type": "TENDER_DOC"},
        )
    assert response.status_code == 200
    assert response.json()["business_type"] == "TENDER_DOC"
    assert response.json()["confirmed"] is True


def test_confirm_type_invalid_rejected(db_session: Session) -> None:
    doc_id, _ = _seed(db_session)
    with _client(db_session) as client:
        response = client.patch(
            f"/api/v1/documents/{doc_id}/type",
            json={"document_id": str(doc_id), "business_type": "INVALID"},
        )
    assert response.status_code == 422


def test_confirm_published_date_success(db_session: Session) -> None:
    _, version_id = _seed(db_session)
    with _client(db_session) as client:
        response = client.patch(
            f"/api/v1/documents/versions/{version_id}/published-date",
            json={"version_id": str(version_id), "published_at": "2026-07-23T00:00:00Z"},
        )
    assert response.status_code == 200
    assert response.json()["published_at"].startswith("2026-07-23")


def test_confirm_published_date_naive_rejected(db_session: Session) -> None:
    _, version_id = _seed(db_session)
    with _client(db_session) as client:
        response = client.patch(
            f"/api/v1/documents/versions/{version_id}/published-date",
            json={"version_id": str(version_id), "published_at": "2026-07-23T00:00:00"},
        )
    assert response.status_code == 400
    assert response.json()["error_code"] == "NAIVE_BUSINESS_TIME"
