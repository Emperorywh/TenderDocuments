"""卡死任务恢复（D-018）。

对 D-017 识别的卡死任务（Worker 心跳过期/崩溃）执行恢复：标记其当前 RUNNING 尝试
FAILED（保留不可变执行历史，不覆盖——SPEC.md 第 11.2 节“重新执行必须生成新的
TaskAttempt，不覆盖失败记录”），并将任务由 RUNNING 转为 RETRY_SCHEDULED（可重试，
待 D-020 重投递 RETRY_SCHEDULED→DISPATCHED）或 FAILED（超过最大重试，终态）。

重试次数按 attempt 计数：已用重试 = 总尝试数 - 1（初始尝试不计重试）。超过 max_retries
则终态 FAILED，否则 RETRY_SCHEDULED 等待重投递。守卫式 UPDATE 保证只对 RUNNING 任务
恢复一次（并发/重复恢复为幂等空操作）。不在内部提交。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID

from sqlalchemy import CursorResult, func, select, update

from tender_insight.modules.analysis.application import RecoveryAction, RecoveryOutcome
from tender_insight.modules.analysis.infrastructure.models import (
    AnalysisTaskModel,
    TaskAttemptModel,
)
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.states import AnalysisTaskStatus

if TYPE_CHECKING:  # 仅类型注解用，避免运行期 ORM 耦合到签名。
    from sqlalchemy.orm import Session

# TaskAttempt 级执行状态（D-005）。
_ATTEMPT_RUNNING = "RUNNING"
_ATTEMPT_FAILED = "FAILED"
# 卡死恢复默认错误码（Worker 心跳过期）。
_DEFAULT_ERROR_CODE = "HEARTBEAT_TIMEOUT"


def recover_stuck_task(
    session: Session,
    task_id: UUID,
    *,
    now: datetime,
    max_retries: int,
    error_code: str = _DEFAULT_ERROR_CODE,
) -> RecoveryOutcome | None:
    """恢复卡死任务；返回恢复结果，非 RUNNING（已恢复/终态）返回 None。

    标记当前 RUNNING 尝试 FAILED（保留），任务 → RETRY_SCHEDULED（可重试）或 → FAILED
    （超 max_retries）。守卫 RUNNING 保证幂等。不在内部提交。
    """
    task = session.get(AnalysisTaskModel, task_id)
    if task is None:
        raise NotFoundError(f"分析任务不存在：{task_id}")
    if task.status != AnalysisTaskStatus.RUNNING.value:
        # 已恢复或已终态，不重复恢复。
        return None

    # 标记当前 RUNNING 尝试 FAILED（保留不可变执行历史）。
    attempt = (
        session.query(TaskAttemptModel)
        .filter_by(analysis_task_id=task_id, status=_ATTEMPT_RUNNING)
        .order_by(TaskAttemptModel.attempt_number.desc())
        .first()
    )
    failed_attempt_number = 0
    if attempt is not None:
        attempt.status = _ATTEMPT_FAILED
        attempt.finished_at = now
        attempt.error_code = error_code
        failed_attempt_number = attempt.attempt_number

    # 已用重试次数 = 总尝试数 - 1（初始尝试不计重试）。
    total_attempts = cast(
        int,
        session.execute(
            select(func.count())
            .select_from(TaskAttemptModel)
            .where(TaskAttemptModel.analysis_task_id == task_id)
        ).scalar_one(),
    )
    retries_used = max(total_attempts - 1, 0)

    if retries_used >= max_retries:
        target_status = AnalysisTaskStatus.FAILED.value
        action = RecoveryAction.FAILED
    else:
        target_status = AnalysisTaskStatus.RETRY_SCHEDULED.value
        action = RecoveryAction.SCHEDULED_RETRY

    # 守卫：仅 RUNNING 可恢复，保证并发/重复恢复幂等。
    recovered = cast(
        CursorResult,
        session.execute(
            update(AnalysisTaskModel)
            .where(
                AnalysisTaskModel.id == task_id,
                AnalysisTaskModel.status == AnalysisTaskStatus.RUNNING.value,
            )
            .values(status=target_status)
            .execution_options(synchronize_session=False)
        ),
    )
    if recovered.rowcount == 0:
        return None

    return RecoveryOutcome(
        task_id=task_id,
        action=action,
        failed_attempt_number=failed_attempt_number,
    )
