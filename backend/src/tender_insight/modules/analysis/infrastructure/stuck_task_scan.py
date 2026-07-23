"""卡死任务扫描（D-017）。

识别心跳过期的 RUNNING 任务：当前 RUNNING 尝试的最近活动时间（heartbeat_at，无则
回退 started_at）早于 now - heartbeat_timeout 的任务，判定为 Worker 卡死/崩溃
（SPEC.md 第 12.2 节“心跳扫描恢复卡死任务”）。回退 started_at 覆盖“领取后未及心跳
即崩溃”的情形（heartbeat_at 为空）。扫描只读，不改状态；恢复（重新领取或失败转换）
属 D-018。timeout 由配置注入，不在领域散落魔法常量。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from tender_insight.modules.analysis.application import StuckTask
from tender_insight.modules.analysis.infrastructure.models import (
    AnalysisTaskModel,
    TaskAttemptModel,
)
from tender_insight.shared.states import AnalysisTaskStatus

if TYPE_CHECKING:  # 仅类型注解用，避免运行期 ORM 耦合到签名。
    from sqlalchemy.orm import Session

# TaskAttempt 级执行状态（D-005）。
_ATTEMPT_RUNNING = "RUNNING"


def find_stuck_tasks(
    session: Session,
    *,
    now: datetime,
    heartbeat_timeout_seconds: float,
) -> list[StuckTask]:
    """返回心跳过期的卡死任务列表（最近活动早于 now - timeout）。

    最近活动 = COALESCE(heartbeat_at, started_at)：有心跳取心跳，否则取执行开始
    （覆盖领取后未刷新心跳即崩溃）。仅扫描任务与尝试均为 RUNNING 的记录（D-013/015
    不变量：RUNNING 尝试对应 RUNNING 任务）。
    """
    threshold = now - timedelta(seconds=heartbeat_timeout_seconds)
    last_activity = func.coalesce(
        TaskAttemptModel.heartbeat_at, TaskAttemptModel.started_at
    )

    rows = (
        session.execute(
            select(TaskAttemptModel, AnalysisTaskModel)
            .join(
                AnalysisTaskModel,
                AnalysisTaskModel.id == TaskAttemptModel.analysis_task_id,
            )
            .where(
                TaskAttemptModel.status == _ATTEMPT_RUNNING,
                AnalysisTaskModel.status == AnalysisTaskStatus.RUNNING.value,
                last_activity < threshold,
            )
            .order_by(TaskAttemptModel.attempt_number)
        )
        .all()
    )

    stuck: list[StuckTask] = []
    for attempt, task in rows:
        activity = attempt.heartbeat_at if attempt.heartbeat_at is not None else attempt.started_at
        stuck.append(
            StuckTask(
                task_id=task.id,
                analysis_run_id=task.analysis_run_id,
                project_id=task.project_id,
                attempt_number=attempt.attempt_number,
                last_activity=activity,
            )
        )
    return stuck
