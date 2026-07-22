"""请求追踪上下文（A-011）。

SPEC.md 第 6.2 节要求关键操作记录包含 request_id；第 12.5 节要求日志、
指标与 Trace 关联 trace_id 等标识。本模块基于 contextvars 提供请求级追踪
上下文，使 API 层设置的 request_id / trace_id 能在应用用例、仓储与日志中
被同一请求的调用链读取，无需把追踪标识层层显式传参。

设计要点：
- 使用 contextvars.ContextVar，在异步与同步调用、线程池中均按上下文隔离；
- trace_id 可缺省，缺省时回退为 request_id，保证至少有一个稳定追踪键；
- 提供 from_headers 适配常见请求头（X-Request-ID、traceparent）。
"""

from __future__ import annotations

import contextlib
import contextvars
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

# W3C traceparent 形如 00-<32 hex trace-id>-<16 hex span-id>-<flags>。
# 仅提取其中的 trace-id 部分。
_TRACEPARENT_RE = re.compile(r"^[0-9a-f]{2}-(?P<trace>[0-9a-f]{32})-")


@dataclass(frozen=True)
class RequestContext:
    """单次请求的追踪上下文。

    request_id 为必填稳定键；trace_id 可选，用于对接外部 Trace 系统。
    """

    request_id: str
    trace_id: str | None = None

    def effective_trace_id(self) -> str:
        """返回有效 trace_id；缺省时回退为 request_id。"""
        return self.trace_id or self.request_id

    @classmethod
    def new(cls, trace_id: str | None = None) -> RequestContext:
        """生成一个带新 request_id 的上下文。"""
        return cls(request_id=uuid.uuid4().hex, trace_id=trace_id)

    @classmethod
    def from_headers(cls, headers: dict[str, str]) -> RequestContext:
        """从入站请求头解析追踪上下文。

        优先使用客户端传入的 X-Request-ID（便于跨系统串联），否则生成新的；
        trace_id 优先取 traceparent 中的 trace-id，其次与 request_id 一致。
        """
        request_id = (headers.get("x-request-id") or "").strip() or uuid.uuid4().hex
        trace_id: str | None = None
        traceparent = (headers.get("traceparent") or "").strip()
        if traceparent:
            match = _TRACEPARENT_RE.match(traceparent)
            if match:
                trace_id = match.group("trace")
        return cls(request_id=request_id, trace_id=trace_id)


# 当前请求上下文按协程/线程隔离存储；默认无上下文。
_current: contextvars.ContextVar[RequestContext | None] = contextvars.ContextVar(
    "tender_request_context", default=None
)


def set_request_context(ctx: RequestContext) -> contextvars.Token[RequestContext | None]:
    """设置当前请求上下文，返回 token 供 reset 使用。"""
    return _current.set(ctx)


def reset_request_context(token: contextvars.Token[RequestContext | None]) -> None:
    """恢复上下文到 set 之前的状态，避免上下文泄漏到下一请求。"""
    _current.reset(token)


def current_request_context() -> RequestContext | None:
    """读取当前请求上下文；未设置时返回 None。"""
    return _current.get()


@contextlib.contextmanager
def request_context_scope(ctx: RequestContext) -> Iterator[RequestContext]:
    """作用域内绑定请求上下文，退出时自动恢复。便于用例与测试使用。"""
    token = set_request_context(ctx)
    try:
        yield ctx
    finally:
        reset_request_context(token)
