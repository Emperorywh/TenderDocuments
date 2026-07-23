"""Worker 任务原子领取（D-013）。

Worker 收到任务消息后，以守卫式 UPDATE 原子领取执行权：仅当任务处于 DISPATCHED 时
置为 RUNNING（DISPATCHED→RUNNING，AnalysisTask 状态机 D-006 的合法领取转换）。
并发消费者对同一任务：数据库行的 UPDATE 串行化，先提交者使 status 变为 RUNNING，
后到者的 WHERE status='DISPATCHED' 不再匹配（0 行），从而“同一消息并发消费只获得
一个执行权”（SPEC.md 第 11.3 节、ADR-004 PostgreSQL 为事实来源）。

领取成功同时新建一条 TaskAttempt（attempt_number 自增、RUNNING、started_at=now），
作为本次执行的不可变记录（D-005）；重复执行永不覆盖旧尝试。本函数不在内部提交，
随 Worker 短事务一起持久化。Celery 不承担业务状态机（ADR-005）。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from sqlalchemy import CursorResult, func, select, update

from tender_insight.modules.analysis.application import ClaimedExecution
from tender_insight.modules.analysis.infrastructure.models import (
    AnalysisTaskModel,
    TaskAttemptModel,
)
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.states import AnalysisTaskStatus

if TYPE_CHECKING:  # 仅类型注解用，避免运行期 ORM 耦合到签名。
    from sqlalchemy.orm import Session

# TaskAttempt 级执行状态（D-005：RUNNING/SUCCEEDED/FAILED，与任务级状态分离）。
_ATTEMPT_RUNNING = "RUNNING"


def claim_task_for_execution(
    session: Session,
    task_id: UUID,
    *,
    now: datetime,
) -> ClaimedExecution | None:
    """原子领取任务执行权；成功返回执行上下文，未获得（已被领取或不在 DISPATCHED）返回 None。

    流程：校验任务存在（缺失抛 NotFoundError）→ 守卫式 UPDATE（DISPATCHED→RUNNING，
    rowcount=0 表示未获得执行权）→ 新建 TaskAttempt（attempt_number 自增）→ 返回
    ClaimedExecution。不在内部提交。
    """
    task = session.get(AnalysisTaskModel, task_id)
    if task is None:
        raise NotFoundError(f"分析任务不存在：{task_id}")

    # 原子守卫：仅 DISPATCHED 可领取为 RUNNING。rowcount=1 表示本消费者获得执行权。
    claimed = cast(
        CursorResult,
        session.execute(
            update(AnalysisTaskModel)
            .where(
                AnalysisTaskModel.id == task_id,
                AnalysisTaskModel.status == AnalysisTaskStatus.DISPATCHED.value,
            )
            .values(status=AnalysisTaskStatus.RUNNING.value)
            .execution_options(synchronize_session=False)
        ),
    )
    if claimed.rowcount == 0:
        # 已被并发消费者领取，或任务不在 DISPATCHED（运行中/终态）。
        return None

    # 本次执行尝试序号：任务内 max(attempt_number)+1，从 1 起。
    max_attempt = session.execute(
        select(func.coalesce(func.max(TaskAttemptModel.attempt_number), 0)).where(
            TaskAttemptModel.analysis_task_id == task_id
        )
    ).scalar_one()
    attempt_number = max_attempt + 1

    session.add(
        TaskAttemptModel(
            id=uuid4(),
            analysis_task_id=task_id,
            attempt_number=attempt_number,
            status=_ATTEMPT_RUNNING,
            started_at=now,
        )
    )

    return ClaimedExecution(
        task_id=task.id,
        analysis_run_id=task.analysis_run_id,
        project_id=task.project_id,
        task_type=task.task_type,
        attempt_number=attempt_number,
    )
