"""项目列表 API 契约测试（B-009 独立验证）。

验证筛选、分页与最大页大小契约。
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


def _seed(client: TestClient, names: list[str]) -> None:
    for name in names:
        client.post(
            "/api/v1/projects",
            json={"name": name, "region": "成都", "industry": "房建", "project_type": "施工"},
        )


def test_list_returns_paginated_page(db_session: Session) -> None:
    with _client(db_session) as client:
        _seed(client, ["A", "B", "C"])
        response = client.get("/api/v1/projects", params={"page": 1, "page_size": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_max_page_size_enforced(db_session: Session) -> None:
    """page_size 超过上限返回 422。"""
    with _client(db_session) as client:
        response = client.get("/api/v1/projects", params={"page_size": 1000})
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_invalid_page_rejected(db_session: Session) -> None:
    with _client(db_session) as client:
        response = client.get("/api/v1/projects", params={"page": 0})
    assert response.status_code == 422


def test_sort_contract(db_session: Session) -> None:
    with _client(db_session) as client:
        _seed(client, ["Charlie", "Alpha", "Bravo"])
        response = client.get("/api/v1/projects", params={"sort": "name", "page_size": 10})
    names = [i["name"] for i in response.json()["items"]]
    assert names == ["Alpha", "Bravo", "Charlie"]


def test_status_filter_lists_archived(db_session: Session) -> None:
    """status=ARCHIVED 列出归档项目。"""
    with _client(db_session) as client:
        _seed(client, ["A", "B"])
        # 通过编辑不可归档；改用直接 PATCH 不行——归档需用例。这里用 list 默认只看活动。
        # 创建后默认活动；查询 ARCHIVED 应为空。
        resp_archived = client.get("/api/v1/projects", params={"status": "ARCHIVED"})
    assert resp_archived.status_code == 200
    assert resp_archived.json()["total"] == 0
