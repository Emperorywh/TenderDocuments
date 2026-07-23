"""操作记录编排辅助（B-017）。

封装“每个命令恰好产生一条结果记录”的事务策略：

- 成功：在命令同一事务内记录 success，与业务变更一起提交（SPEC.md 第 5.2 节）。
- 失败：回滚业务事务后，在**独立会话/事务**中记录 failure 与稳定错误码，再抛出
  原异常，保证失败记录不被业务回滚带走（SPEC.md 第 6.2 节要求记录结果与错误码）。

为保持应用层不直接依赖 ORM，会话与录制器由调用方以可调用对象注入
（open_recorder(session) -> OperationRecorder）。本模块运行期仅依赖纯模块。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

from tender_insight.modules.operation_log.application import OperationRecord, OperationRecorder
from tender_insight.shared.domain_error import DomainError

if TYPE_CHECKING:  # 仅类型注解用，避免运行期 ORM 耦合。
    from sqlalchemy.orm import Session

T = TypeVar("T")


def record_command_outcome(
    *,
    session: Session,
    action: str,
    resource_type: str,
    resource_id: str,
    request_id: str | None,
    perform: Callable[[], T],
    session_factory: Callable[[], Session] | None = None,
    open_recorder: Callable[[Session], OperationRecorder] | None = None,
) -> T:
    """执行命令并在成功/失败时各产生恰好一条操作记录（当提供录制器时）。

    perform 执行业务变更与仓储暂存（不提交）；成功时本函数提交。
    未提供 session_factory/open_recorder 时跳过记录，仅负责提交/回滚，
    便于不关心记录的用例复用同一事务边界。
    """
    try:
        result = perform()
    except DomainError as exc:
        session.rollback()
        if open_recorder is not None and session_factory is not None:
            persist_operation_failure(
                session_factory=session_factory,
                open_recorder=open_recorder,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                error_code=exc.code,
                request_id=request_id,
            )
        raise
    except Exception:
        session.rollback()
        if open_recorder is not None and session_factory is not None:
            persist_operation_failure(
                session_factory=session_factory,
                open_recorder=open_recorder,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                error_code="INTERNAL_ERROR",
                request_id=request_id,
            )
        raise

    # 成功：同事务记录（若提供录制器）并提交。
    if open_recorder is not None:
        open_recorder(session).record(
            OperationRecord(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                result="success",
                request_id=request_id,
            )
        )
    session.commit()
    return result


def persist_operation_failure(
    *,
    session_factory: Callable[[], Session],
    open_recorder: Callable[[Session], OperationRecorder],
    action: str,
    resource_type: str,
    resource_id: str,
    error_code: str,
    request_id: str | None,
) -> None:
    """在独立会话中持久化失败记录，确保不受业务事务回滚影响。

    供 record_command_outcome 与需要自定义事务边界（如对象存储副作用回滚）的
    用例复用，使“失败记录独立持久化”只有这一处权威实现（SPEC.md 第 6.2 节）。
    """
    fresh = session_factory()
    try:
        open_recorder(fresh).record(
            OperationRecord(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                result="failure",
                error_code=error_code,
                request_id=request_id,
            )
        )
        fresh.commit()
    finally:
        fresh.close()
