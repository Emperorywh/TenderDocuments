"""统一错误契约测试（A-012 独立验证）。

验证两个示例失败返回同一结构，且以 error_code/status 判定，无需匹配文案。
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tender_insight.shared.errors import (
    ConflictError,
    DomainError,
    ErrorCode,
    NotFoundError,
    ProblemDetail,
    add_problem_exception_handler,
    problem_from_error,
)

# 两个示例领域失败：文案不同、错误码与状态不同，但结构相同。
_EXAMPLE_FAILURES: list[DomainError] = [
    NotFoundError("找不到项目 abc"),
    ConflictError("版本号已过期"),
]


def test_two_failures_share_structure_without_matching_text() -> None:
    """两个示例失败映射后字段集合一致；判定基于 error_code/status，不基于文案。"""
    problems = [problem_from_error(exc) for exc in _EXAMPLE_FAILURES]

    # 结构一致：字段集合完全相同。
    keys = {tuple(sorted(p.model_dump().keys())) for p in problems}
    assert len(keys) == 1, "两个失败响应字段结构不一致"

    # 错误码与状态按预期不同，且均来自稳定目录。
    codes = {p.error_code for p in problems}
    assert codes == {ErrorCode.NOT_FOUND.value, ErrorCode.CONFLICT.value}
    statuses = {p.status for p in problems}
    assert statuses == {404, 409}

    # 不以文案判定：detail 各自不同，这里只确认其存在且非空。
    for p in problems:
        assert p.detail


def test_problem_detail_required_fields() -> None:
    problem = problem_from_error(NotFoundError("x"))
    assert isinstance(problem, ProblemDetail)
    assert problem.type == "about:blank"
    assert problem.error_code == ErrorCode.NOT_FOUND.value


def test_unknown_exception_maps_to_internal_error() -> None:
    """非 DomainError 异常统一归为 INTERNAL_ERROR，不泄漏内部细节。"""
    problem = problem_from_error(RuntimeError("数据库连接串 postgres://user:pwd"))
    assert problem.error_code == ErrorCode.INTERNAL_ERROR.value
    assert problem.status == 500
    # detail 不包含原始异常的敏感细节。
    assert "postgres://user:pwd" not in problem.detail


def test_fastapi_handler_returns_problem_json() -> None:
    """挂载处理器后，领域异常返回 application/problem+json 与稳定结构。"""
    app = FastAPI()

    @app.get("/raise-not-found")
    def _raise_nf() -> None:
        raise NotFoundError("项目不存在")

    @app.get("/raise-conflict")
    def _raise_c() -> None:
        raise ConflictError("版本冲突")

    add_problem_exception_handler(app)

    with TestClient(app) as client:
        nf = client.get("/raise-not-found")
        cfl = client.get("/raise-conflict")

    assert nf.status_code == 404
    assert nf.headers["content-type"].startswith("application/problem+json")
    assert nf.json()["error_code"] == ErrorCode.NOT_FOUND.value

    assert cfl.status_code == 409
    assert cfl.json()["error_code"] == ErrorCode.CONFLICT.value

    # 两个响应结构一致（键集合相同）。
    assert set(nf.json().keys()) == set(cfl.json().keys())
