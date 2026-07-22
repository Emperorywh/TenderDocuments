"""业务入口无鉴权契约测试（B-019）。

SPEC.md 第 6.1、15.1 节要求：业务 API 不要求 Bearer Token、身份 Cookie 或
用户/组织请求头。本测试在不提供任何鉴权头/Cookie 的情况下调用各业务接口，
确认其正常工作（非 401/403），作为长期无鉴权回归护栏。
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tender_insight.bootstrap.db import get_session
from tender_insight.main import create_app
from tender_insight.modules.operation_log.api import create_router as operation_log_router
from tender_insight.modules.project.api import create_router as project_router
from tender_insight.shared.errors import add_problem_exception_handler


def _client(session: Session) -> TestClient:
    app = create_app()
    app.include_router(project_router())
    app.include_router(operation_log_router())
    add_problem_exception_handler(app)
    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_health_without_auth(db_session: Session) -> None:
    """健康检查无需鉴权。"""
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200


def test_business_apis_work_without_auth_headers(db_session: Session) -> None:
    """不提供 Token/Cookie/用户头时业务接口正常工作。"""
    with _client(db_session) as client:
        # 显式不带 Authorization/Cookie，并模拟客户端仅发普通请求。
        list_resp = client.get("/api/v1/projects")
        assert list_resp.status_code == 200

        create_resp = client.post(
            "/api/v1/projects",
            json={"name": "p", "region": "成都", "industry": "房建", "project_type": "施工"},
        )
        assert create_resp.status_code == 201

        logs_resp = client.get("/api/v1/operation-logs")
        assert logs_resp.status_code == 200


def test_no_auth_middleware_present() -> None:
    """应用未注册鉴权中间件/依赖。"""
    from starlette.middleware.base import BaseHTTPMiddleware  # noqa: F401

    app = create_app()
    # 收集所有用户中间件类名，断言无常见鉴权中间件。
    mw_names = {getattr(m.cls, "__name__", "") for m in app.user_middleware}
    auth_markers = ("AuthenticationMiddleware", "AuthMiddleware", "BearerAuthMiddleware")
    assert not any(name in mw_names for name in auth_markers), f"存在鉴权中间件：{mw_names}"


def test_request_with_arbitrary_auth_header_still_works(db_session: Session) -> None:
    """即使客户端误带 Authorization 头，业务仍正常（后端不校验身份）。"""
    with _client(db_session) as client:
        response = client.get(
            "/api/v1/projects",
            headers={"Authorization": "Bearer some-token", "X-User-Id": "u-1"},
        )
    assert response.status_code == 200
