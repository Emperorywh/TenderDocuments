"""原始文件访问 API 契约测试（C-033 独立验证）。

验证地址签发成功、到期时间来自配置、响应不暴露内部对象键，未知版本 404。
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


def _client(session: Session, storage: MagicMock) -> TestClient:
    app = create_app()
    app.include_router(document_router())
    add_problem_exception_handler(app)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_object_storage] = lambda: storage
    return TestClient(app)


def _storage(url: str = "https://minio.local/download") -> MagicMock:
    storage = MagicMock()
    storage.presigned_get_url.return_value = url
    return storage


def _seed_version(session: Session, object_key: str = "original/abc-uuid") -> Uuid:
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
    doc = Document(
        id=Uuid.new(),
        project_id=pid,
        business_type=DocumentBusinessType.OTHER,
        name="t.pdf",
    )
    SqlAlchemyDocumentRepository(session).add(doc)
    session.commit()
    version = DocumentVersion.create(
        version_id=Uuid.new(),
        document_id=doc.id,
        version_number=1,
        original_object_key=object_key,
        sha256="a" * 64,
        size_bytes=10,
        mime="application/pdf",
    )
    SqlAlchemyDocumentVersionRepository(session).add(version)
    session.commit()
    return version.id


def test_original_url_success(db_session: Session) -> None:
    """签发成功返回 200 与短期地址，响应不含内部对象键。"""
    version_id = _seed_version(db_session)
    storage = _storage()
    with _client(db_session, storage) as client:
        response = client.get(f"/api/v1/documents/versions/{version_id}/original-url")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"download_url", "expires_at", "method"}
    assert body["download_url"] == "https://minio.local/download"
    assert body["method"] == "GET"
    # 响应不暴露内部对象键（无 object_key / 内部路径字段）。
    forbidden = {"object_key", "key", "internal_key"}
    assert not (forbidden & set(body))


def test_original_url_called_with_configured_ttl(db_session: Session) -> None:
    """presigned_get_url 以配置 TTL 调用（地址到期由对象存储据此校验）。"""
    from tender_insight.bootstrap.config import get_settings

    version_id = _seed_version(db_session)
    storage = _storage()
    with _client(db_session, storage) as client:
        client.get(f"/api/v1/documents/versions/{version_id}/original-url")

    storage.presigned_get_url.assert_called_once()
    _, kwargs = storage.presigned_get_url.call_args
    assert kwargs["expires_in_seconds"] == get_settings().presigned_url_ttl_seconds


def test_original_url_unknown_version_returns_404(db_session: Session) -> None:
    with _client(db_session, _storage()) as client:
        response = client.get(
            f"/api/v1/documents/versions/{Uuid.new()}/original-url"
        )
    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"
