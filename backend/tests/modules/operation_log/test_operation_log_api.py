"""操作记录查询 API 契约测试（B-018 独立验证）。

验证可按 project_id 与动作筛选，且响应不含虚构操作者。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tender_insight.bootstrap.db import get_session
from tender_insight.main import create_app
from tender_insight.modules.operation_log.api import create_router as operation_log_router
from tender_insight.modules.operation_log.application import OperationRecord
from tender_insight.modules.operation_log.infrastructure.recorder import (
    SqlAlchemyOperationRecorder,
)
from tender_insight.modules.project.api import create_router as project_router
from tender_insight.shared.errors import add_problem_exception_handler


def _client(session: Session) -> TestClient:
    app = create_app()
    app.include_router(project_router())
    app.include_router(operation_log_router())
    add_problem_exception_handler(app)
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def _seed_logs(session: Session) -> str:
    recorder = SqlAlchemyOperationRecorder(session)
    recorder.record(
        OperationRecord(
            action="project.create",
            resource_type="project",
            resource_id="proj-1",
            result="success",
            request_id="req-1",
        )
    )
    recorder.record(
        OperationRecord(
            action="project.archive",
            resource_type="project",
            resource_id="proj-1",
            result="success",
            request_id="req-2",
        )
    )
    recorder.record(
        OperationRecord(
            action="project.create",
            resource_type="project",
            resource_id="proj-2",
            result="failure",
            error_code="INVALID_PROJECT_DATA",
        )
    )
    session.commit()
    return "proj-1"


def test_filter_by_project_id(db_session: Session) -> None:
    _seed_logs(db_session)
    with _client(db_session) as client:
        response = client.get("/api/v1/operation-logs", params={"project_id": "proj-1"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert all(item["resource_id"] == "proj-1" for item in body["items"])


def test_filter_by_action(db_session: Session) -> None:
    _seed_logs(db_session)
    with _client(db_session) as client:
        response = client.get("/api/v1/operation-logs", params={"action": "project.create"})
    body = response.json()
    assert body["total"] == 2
    assert all(item["action"] == "project.create" for item in body["items"])


def test_response_has_no_operator_fields(db_session: Session) -> None:
    _seed_logs(db_session)
    with _client(db_session) as client:
        response = client.get("/api/v1/operation-logs", params={"page_size": 10})
    items = response.json()["items"]
    assert items
    # 响应项不含身份/操作者字段。
    forbidden = {"user_id", "operator", "operator_id", "created_by", "reviewed_by", "organization_id"}
    for item in items:
        assert not (forbidden & set(item)), f"响应含身份字段：{forbidden & set(item)}"


def test_pagination_and_sort(db_session: Session) -> None:
    _seed_logs(db_session)
    with _client(db_session) as client:
        response = client.get("/api/v1/operation-logs", params={"page": 1, "page_size": 2})
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    # 按 occurred_at desc：第一条不早于第二条。
    assert body["items"][0]["occurred_at"] >= body["items"][1]["occurred_at"]
