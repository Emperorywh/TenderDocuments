"""项目编辑 API 契约测试（B-007 独立验证）。

验证成功与版本冲突响应均符合契约。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tender_insight.bootstrap.db import get_session
from tender_insight.main import create_app
from tender_insight.modules.project.api import create_router
from tender_insight.shared.errors import add_problem_exception_handler


def _client(session: Session) -> TestClient:
    app = create_app()
    app.include_router(create_router())
    add_problem_exception_handler(app)
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def _create(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/projects",
        json={"name": "p", "region": "成都", "industry": "房建", "project_type": "施工"},
    )
    return resp.json()["project_id"]


def test_edit_success(db_session: Session) -> None:
    """正确版本编辑返回 200 与结果。"""
    with _client(db_session) as client:
        pid = _create(client)
        response = client.patch(
            f"/api/v1/projects/{pid}",
            json={"expected_version": 1, "name": "改名"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "改名"
    assert body["version"] == 2


def test_edit_version_conflict(db_session: Session) -> None:
    """版本冲突返回 409 CONFLICT Problem Details。"""
    with _client(db_session) as client:
        pid = _create(client)
        # 先改一次：1 -> 2。
        client.patch(f"/api/v1/projects/{pid}", json={"expected_version": 1, "name": "第一次"})
        # 再用过期版本：应冲突。
        response = client.patch(
            f"/api/v1/projects/{pid}",
            json={"expected_version": 1, "name": "冲突"},
        )
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["error_code"] == "CONFLICT"


def test_edit_not_found(db_session: Session) -> None:
    import uuid

    with _client(db_session) as client:
        response = client.patch(
            f"/api/v1/projects/{uuid.uuid4()}",
            json={"expected_version": 1, "name": "x"},
        )
    assert response.status_code == 404
    assert response.json()["error_code"] == "NOT_FOUND"


def test_edit_invalid_field(db_session: Session) -> None:
    with _client(db_session) as client:
        pid = _create(client)
        response = client.patch(
            f"/api/v1/projects/{pid}",
            json={"expected_version": 1, "name": "   "},
        )
    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_PROJECT_DATA"
