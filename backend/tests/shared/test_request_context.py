"""请求追踪上下文测试（A-011 独立验证）。

验证 API 层设置的追踪标识可在应用用例中读取为同一值。
"""

from __future__ import annotations

from tender_insight.shared.request_context import (
    RequestContext,
    current_request_context,
    request_context_scope,
)


def _app_layer_reads_context() -> str | None:
    """模拟应用用例：直接读取当前请求上下文，而非通过参数传入。"""
    ctx = current_request_context()
    return ctx.request_id if ctx is not None else None


def test_context_propagates_from_api_to_use_case() -> None:
    """API 层设置上下文后，应用用例读取到同一 request_id。"""
    ctx = RequestContext.new()
    with request_context_scope(ctx):
        assert _app_layer_reads_context() == ctx.request_id


def test_context_cleared_after_scope() -> None:
    """作用域结束后上下文恢复为 None，不泄漏到下一请求。"""
    ctx = RequestContext.new()
    assert current_request_context() is None
    with request_context_scope(ctx):
        assert current_request_context() is not None
    assert current_request_context() is None


def test_trace_id_defaults_to_request_id() -> None:
    """未提供 trace_id 时，有效 trace_id 回退为 request_id。"""
    ctx = RequestContext(request_id="req-1")
    assert ctx.trace_id is None
    assert ctx.effective_trace_id() == "req-1"


def test_from_headers_uses_x_request_id() -> None:
    ctx = RequestContext.from_headers({"x-request-id": "abc-123"})
    assert ctx.request_id == "abc-123"


def test_from_headers_generates_id_when_missing() -> None:
    ctx = RequestContext.from_headers({})
    assert ctx.request_id
    assert len(ctx.request_id) == 32  # uuid4 hex


def test_from_headers_extracts_traceparent() -> None:
    """从 W3C traceparent 头提取 trace-id。"""
    tp = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    ctx = RequestContext.from_headers({"traceparent": tp})
    assert ctx.trace_id == "0af7651916cd43dd8448eb211c80319c"


def test_new_generates_distinct_ids() -> None:
    a = RequestContext.new()
    b = RequestContext.new()
    assert a.request_id != b.request_id
