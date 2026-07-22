"""项目创建 API 契约测试（B-005 独立验证）。

验证请求、响应与错误码符合契约（统一 Problem Details）。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tender_insight.bootstrap.db import get_session
from tender_insight.main import create_app
from tender_insight.modules.project.api import create_router
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.shared.errors import add_problem_exception_handler


def _client_with_session(session: Session) -> TestClient:
    app = create_app()
    app.include_router(create_router())
    add_problem_exception_handler(app)
    # 覆盖会话依赖，指向测试库会话。
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_create_project_success(db_session: Session) -> None:
    """合法请求返回 201 与结果契约。"""
    with _client_with_session(db_session) as client:
        response = client.post(
            "/api/v1/projects",
            json={
                "name": "天府新区房建",
                "region": "成都",
                "industry": "房屋建筑工程",
                "project_type": "施工",
            },
        )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"project_id", "name", "region", "industry", "project_type"}
    assert body["name"] == "天府新区房建"
    assert body["project_id"]
    # 已落库。
    assert db_session.query(ProjectModel).count() == 1


def test_missing_required_field_returns_problem_422(db_session: Session) -> None:
    """缺少必填字段返回 422 VALIDATION_ERROR Problem Details。"""
    with _client_with_session(db_session) as client:
        response = client.post(
            "/api/v1/projects",
            json={"name": "p", "region": "成都", "industry": "房建"},  # 缺 project_type
        )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["error_code"] == "VALIDATION_ERROR"
    assert "project_type" in body["detail"]


def test_whitespace_field_returns_problem_400(db_session: Session) -> None:
    """空白字段（通过 Pydantic）被领域拒绝，返回 400 INVALID_PROJECT_DATA。"""
    with _client_with_session(db_session) as client:
        response = client.post(
            "/api/v1/projects",
            json={"name": "   ", "region": "成都", "industry": "房建", "project_type": "施工"},
        )
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["error_code"] == "INVALID_PROJECT_DATA"
    # 失败不落库。
    assert db_session.query(ProjectModel).count() == 0


def test_openapi_documents_create_endpoint(db_session: Session) -> None:
    """OpenAPI 契约包含创建接口。"""
    app = create_app()
    app.include_router(create_router())
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    assert "/api/v1/projects" in schema["paths"]
    assert "post" in schema["paths"]["/api/v1/projects"]
