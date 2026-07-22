"""统一错误契约（A-012）。

SPEC.md 第 8.1 节要求错误响应采用统一 Problem Details 结构并包含稳定
error_code。本模块提供：

- ErrorCode：稳定错误码目录，作为前后端契约的枚举来源；
- DomainError 及常用子类：领域层抛出的异常基类，携带 error_code 与 HTTP 状态；
- ProblemDetail：RFC 7807 风格的统一错误响应模型；
- problem_from_error：把异常映射为 ProblemDetail；
- add_problem_exception_handler：把映射挂到 FastAPI，统一返回
  application/problem+json。

错误判定以 error_code 与 status 为准，不依赖 detail 文案，使契约稳定、可自动化校验。
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from tender_insight.shared.request_context import current_request_context
from tender_insight.shared.state_transitions import InvalidTransitionError


class ErrorCode(StrEnum):
    """稳定错误码目录。新增错误必须在此登记，禁止散落魔法字符串。"""

    # 输入与值对象校验。
    INVALID_UUID = "INVALID_UUID"
    NAIVE_BUSINESS_TIME = "NAIVE_BUSINESS_TIME"
    INVALID_MONEY = "INVALID_MONEY"
    INVALID_SCORE = "INVALID_SCORE"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # 资源与并发。
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"

    # 状态机与业务规则。
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    UNPUBLISHABLE = "UNPUBLISHABLE"

    # 未分类内部错误。
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DomainError(Exception):
    """领域错误基类。

    子类固定自己的 error_code、http_status 与 title；detail 由抛出点提供具体信息。
    """

    error_code: ErrorCode = ErrorCode.INTERNAL_ERROR
    http_status: int = 400
    title: str = "领域错误"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    error_code = ErrorCode.NOT_FOUND
    http_status = 404
    title = "资源不存在"


class ConflictError(DomainError):
    error_code = ErrorCode.CONFLICT
    http_status = 409
    title = "资源冲突"


class StateTransitionError(DomainError):
    error_code = ErrorCode.INVALID_STATE_TRANSITION
    http_status = 409
    title = "非法状态转换"


class ProblemDetail(BaseModel):
    """RFC 7807 风格的统一错误响应。

    error_code 与 status 是契约稳定键；detail 为人类可读说明，不作为判定依据。
    instance 记录 request_id，trace_id 关联分布式追踪。
    """

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    error_code: str
    instance: str | None = None
    trace_id: str | None = None


def problem_from_error(exc: Exception) -> ProblemDetail:
    """把任意异常映射为 ProblemDetail。

    DomainError 子类按其声明的 error_code/status 映射；状态转换非法错误
    （InvalidTransitionError，来自纯层）映射为 409 INVALID_STATE_TRANSITION；
    其它异常统一归为 INTERNAL_ERROR（500），避免把内部异常细节直接暴露给调用方。
    """
    ctx = current_request_context()
    instance = ctx.request_id if ctx is not None else None
    trace_id = ctx.effective_trace_id() if ctx is not None else None

    if isinstance(exc, InvalidTransitionError):
        return ProblemDetail(
            title="非法状态转换",
            status=409,
            detail=str(exc),
            error_code=ErrorCode.INVALID_STATE_TRANSITION.value,
            instance=instance,
            trace_id=trace_id,
        )

    if isinstance(exc, DomainError):
        return ProblemDetail(
            title=exc.title,
            status=exc.http_status,
            detail=exc.detail,
            error_code=exc.error_code.value,
            instance=instance,
            trace_id=trace_id,
        )

    # 非领域异常：对外不泄漏内部细节，仅返回通用信息。
    return ProblemDetail(
        title="内部错误",
        status=500,
        detail="服务遇到内部错误",
        error_code=ErrorCode.INTERNAL_ERROR.value,
        instance=instance,
        trace_id=trace_id,
    )


def add_problem_exception_handler(app: FastAPI) -> None:
    """将 DomainError 与未知异常统一映射为 Problem Details 响应。"""

    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        problem = problem_from_error(exc)
        return JSONResponse(
            status_code=problem.status,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    @app.exception_handler(InvalidTransitionError)
    async def _handle_invalid_transition(_: Request, exc: InvalidTransitionError) -> JSONResponse:
        problem = problem_from_error(exc)
        return JSONResponse(
            status_code=problem.status,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def _handle_unknown(_: Request, exc: Exception) -> JSONResponse:
        problem = problem_from_error(exc)
        return JSONResponse(
            status_code=problem.status,
            content=problem.model_dump(exclude_none=True),
            media_type="application/problem+json",
        )
