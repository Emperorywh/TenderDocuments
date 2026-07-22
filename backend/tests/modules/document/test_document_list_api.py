"""文件列表 API 契约测试（C-029 独立验证）。

验证分页、版本数与确认状态响应符合契约。
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
from tender_insight.modules.document.infrastructure.document_repositories import (
    SqlAlchemyDocumentRepository,
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


def test_list_documents_paginated(db_session: Session) -> None:
    pid = Uuid.new()
    db_session.add(
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
    db_session.commit()
    doc_repo = SqlAlchemyDocumentRepository(db_session)
    for name in ["a.pdf", "b.pdf", "c.pdf"]:
        doc_repo.add(
            Document(
                id=Uuid.new(),
                project_id=pid,
                business_type=DocumentBusinessType.TENDER_DOC,
                name=name,
            )
        )
    db_session.commit()

    with _client(db_session) as client:
        response = client.get(f"/api/v1/projects/{pid}/documents", params={"page_size": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    item = body["items"][0]
    assert set(item) == {
        "document_id",
        "project_id",
        "business_type",
        "name",
        "confirmed",
        "version_count",
        "created_at",
    }
    assert item["confirmed"] is True
    assert item["version_count"] == 0


def test_max_page_size_enforced(db_session: Session) -> None:
    pid = Uuid.new()
    db_session.add(
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
    db_session.commit()
    with _client(db_session) as client:
        response = client.get(
            f"/api/v1/projects/{pid}/documents", params={"page_size": 1000}
        )
    assert response.status_code == 422
