"""文件关系 API 契约测试（C-032 独立验证）。

验证循环关系与跨项目返回稳定错误码。
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


def _seed(session: Session, pid: Uuid) -> Uuid:
    doc = Document(
        id=Uuid.new(), project_id=pid, business_type=DocumentBusinessType.TENDER_DOC, name="t.pdf"
    )
    repo = SqlAlchemyDocumentRepository(session)
    repo.add(doc)
    session.commit()
    return doc.id


def _seed_project(session: Session) -> Uuid:
    pid = Uuid.new()
    session.add(
        ProjectModel(
            id=pid.value,
            name="p", region="成都", industry="房建", project_type="施工",
            lifecycle_state="ACTIVE", version=1,
        )
    )
    session.commit()
    return pid


def test_relation_created(db_session: Session) -> None:
    pid = _seed_project(db_session)
    a = _seed(db_session, pid)
    b = _seed(db_session, pid)
    with _client(db_session) as client:
        response = client.post(
            "/api/v1/documents/relations",
            json={
                "project_id": str(pid),
                "source_document_id": str(a),
                "target_document_id": str(b),
                "relation_type": "REPLACES",
            },
        )
    assert response.status_code == 201


def test_cycle_returns_409(db_session: Session) -> None:
    """循环替代返回 409 CONFLICT。"""
    pid = _seed_project(db_session)
    a = _seed(db_session, pid)
    b = _seed(db_session, pid)
    with _client(db_session) as client:
        client.post(
            "/api/v1/documents/relations",
            json={"project_id": str(pid), "source_document_id": str(a),
                  "target_document_id": str(b), "relation_type": "REPLACES"},
        )
        response = client.post(
            "/api/v1/documents/relations",
            json={"project_id": str(pid), "source_document_id": str(b),
                  "target_document_id": str(a), "relation_type": "REPLACES"},
        )
    assert response.status_code == 409
    assert response.json()["error_code"] == "CONFLICT"


def test_cross_project_returns_409(db_session: Session) -> None:
    """跨项目关系返回 409。"""
    p1 = _seed_project(db_session)
    p2 = _seed_project(db_session)
    a = _seed(db_session, p1)
    b = _seed(db_session, p2)
    with _client(db_session) as client:
        response = client.post(
            "/api/v1/documents/relations",
            json={"project_id": str(p1), "source_document_id": str(a),
                  "target_document_id": str(b), "relation_type": "SUPPLEMENTS"},
        )
    assert response.status_code == 409
