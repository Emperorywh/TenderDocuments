"""任务幂等结果提交（D-015）。

Worker 执行完成后提交结果：守卫式 UPDATE 将任务由 RUNNING 置为 SUCCEEDED（成功）或
FAILED（终态失败），并标记当前执行尝试完成（finished_at、status、error_code）。重复
消息（任务已终态）的再次提交为幂等空操作（rowcount=0，返回 False），不产生重复正式
结果（SPEC.md 第 11.3 节“重复任务消息不会生成重复业务结果”）。

守卫式 UPDATE ... WHERE status='RUNNING' 保证“只提交一次”：并发或重复提交中，先到者
使任务离开 RUNNING，后到者不再匹配（与 D-013 领取一致的原子模式）。可重试失败
（RUNNING→RETRY_SCHEDULED）属 D-019 错误分类与 D-020 重试调度，不在本任务范围。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID

from sqlalchemy import CursorResult, desc, update

from tender_insight.modules.analysis.infrastructure.models import (
    AnalysisTaskModel,
    TaskAttemptModel,
)
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.states import AnalysisTaskStatus

if TYPE_CHECKING:  # 仅类型注解用，避免运行期 ORM 耦合到签名。
    from sqlalchemy.orm import Session

# TaskAttempt 级执行状态（D-005：RUNNING/SUCCEEDED/FAILED）。
_ATTEMPT_RUNNING = "RUNNING"
_ATTEMPT_SUCCEEDED = "SUCCEEDED"
_ATTEMPT_FAILED = "FAILED"


def submit_task_result(
    session: Session,
    task_id: UUID,
    *,
    succeeded: bool,
    error_code: str | None = None,
    now: datetime,
) -> bool:
    """幂等提交任务结果；返回是否本次 newly 提交（重复/已终态返回 False）。

    成功 → SUCCEEDED；失败 → FAILED（终态）。重复提交为幂等空操作（不重复产出结果）。
    失败时 error_code 记录稳定错误分类（D-019）。不在内部提交。
    """
    if session.get(AnalysisTaskModel, task_id) is None:
        raise NotFoundError(f"分析任务不存在：{task_id}")

    new_status = (
        AnalysisTaskStatus.SUCCEEDED.value if succeeded else AnalysisTaskStatus.FAILED.value
    )
    # 守卫：仅 RUNNING 可提交结果。rowcount=0 表示已提交（终态），幂等空操作。
    submitted = cast(
        CursorResult,
        session.execute(
            update(AnalysisTaskModel)
            .where(
                AnalysisTaskModel.id == task_id,
                AnalysisTaskModel.status == AnalysisTaskStatus.RUNNING.value,
            )
            .values(status=new_status)
            .execution_options(synchronize_session=False)
        ),
    )
    if submitted.rowcount == 0:
        return False

    # 标记当前执行尝试（最新 RUNNING attempt）完成，保留不可变执行历史（D-005）。
    attempt = (
        session.query(TaskAttemptModel)
        .filter_by(analysis_task_id=task_id, status=_ATTEMPT_RUNNING)
        .order_by(desc(TaskAttemptModel.attempt_number))
        .first()
    )
    if attempt is not None:
        attempt.status = _ATTEMPT_SUCCEEDED if succeeded else _ATTEMPT_FAILED
        attempt.finished_at = now
        attempt.error_code = None if succeeded else error_code

    return True
