"""健康检查固定契约测试（A-003 独立验证）。

验证进程启动后 /health 返回稳定契约：字段集合、取值与 HTTP 状态均固定，
且与未来 /api/v1 业务接口分离。使用 FastAPI TestClient 在进程内驱动 ASGI
应用，等价于 uvicorn 实际对外提供的响应。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tender_insight import __version__
from tender_insight.main import HealthResponse, create_app


def test_health_returns_fixed_contract() -> None:
    """GET /health 返回固定的存活契约。"""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")

    # 状态码固定 200。
    assert response.status_code == 200
    # 响应体精确等于固定契约，避免后续无意新增字段而不向后兼容。
    assert response.json() == {
        "status": "ok",
        "service": "tender-insight-api",
        "version": __version__,
    }


def test_health_contract_matches_schema() -> None:
    """固定契约可通过 HealthResponse 模型解析。"""
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")

    parsed = HealthResponse.model_validate(response.json())
    assert parsed.status == "ok"
    assert parsed.service == "tender-insight-api"
    assert parsed.version == __version__


def test_business_routes_are_separate_from_health() -> None:
    """健康检查不在 /api/v1 业务前缀下，二者必须分离（SPEC.md 第 6.1 节）。"""
    app = create_app()
    routes = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/health" in routes
    # 首版尚未注册业务路由；确保没有任何路由错误地复用健康检查路径语义。
    assert all(not path.startswith("/api/v1") for path in routes)
