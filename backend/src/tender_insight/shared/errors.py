"""统一错误契约（A-012，B-005 重构）。

SPEC.md 第 8.1 节要求错误响应采用统一 Problem Details 结构并包含稳定
error_code。本模块提供：

- ErrorCode：稳定错误码目录（转定义于纯模块 shared.error_codes，此处再导出
  以兼容历史导入）；
- DomainError 及常用子类：领域错误，携带 code/http_status/title；
- ProblemDetail：RFC 7807 风格统一错误响应；
- problem_from_error：异常 → ProblemDetail 映射；
- add_problem_exception_handler：FastAPI 处理器，统一返回
  application/problem+json。

错误判定以 error_code 与 status 为准，不依赖 detail 文案。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from tender_insight.shared.domain_error import DomainError
from tender_insight.shared.error_codes import ErrorCode
from tender_insight.shared.request_context import current_request_context

# 兼容历史导入：ErrorCode 仍可经本模块访问。
__all__ = [
    "ErrorCode",
    "DomainError",
    "NotFoundError",
    "ConflictError",
    "PreconditionFailedError",
    "ProblemDetail",
    "problem_from_error",
    "add_problem_exception_handler",
]


class NotFoundError(DomainError):
    code = ErrorCode.NOT_FOUND.value
    http_status = 404
    title = "资源不存在"


class ConflictError(DomainError):
    code = ErrorCode.CONFLICT.value
    http_status = 409
    title = "资源冲突"


class PreconditionFailedError(DomainError):
    code = ErrorCode.PRECONDITION_FAILED.value
    http_status = 412
    title = "前置条件不满足"


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
    """把异常映射为 ProblemDetail。

    DomainError 子类按其声明的 code/http_status/title 映射；其它异常统一归为
    INTERNAL_ERROR（500），不把内部异常细节直接暴露给调用方。
    """
    ctx = current_request_context()
    instance = ctx.request_id if ctx is not None else None
    trace_id = ctx.effective_trace_id() if ctx is not None else None

    if isinstance(exc, DomainError):
        return ProblemDetail(
            title=exc.title,
            status=exc.http_status,
            detail=exc.detail,
            error_code=exc.code,
            instance=instance,
            trace_id=trace_id,
        )

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

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # 将 FastAPI 请求体校验错误统一为 Problem Details，含稳定 error_code。
        detail = "；".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        ctx = current_request_context()
        problem = ProblemDetail(
            title="请求校验失败",
            status=422,
            detail=detail,
            error_code=ErrorCode.VALIDATION_ERROR.value,
            instance=ctx.request_id if ctx is not None else None,
            trace_id=ctx.effective_trace_id() if ctx is not None else None,
        )
        return JSONResponse(
            status_code=422,
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
