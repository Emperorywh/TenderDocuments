"""Worker 任务归属校验（D-014）。

Worker 不信任消息中的孤立 ID（SPEC.md 第 4.3 节）：收到任务消息后，以消息声称的
task_id/run_id/project_id 与数据库权威交叉校验——任务确属该运行、运行确属该项目、
且任务与运行同属一项目。任一不一致即判定消息伪造或不一致，抛 TaskOwnershipError
拒绝执行（不领取、不产出结果）。

数据库是业务状态唯一事实来源（ADR-004）；消息只用于定位，归属以数据库为准。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from tender_insight.modules.analysis.application import TaskOwnership
from tender_insight.modules.analysis.domain.exceptions import TaskOwnershipError
from tender_insight.modules.analysis.infrastructure.models import (
    AnalysisRunModel,
    AnalysisTaskModel,
)
from tender_insight.shared.errors import NotFoundError

if TYPE_CHECKING:  # 仅类型注解用，避免运行期 ORM 耦合到签名。
    from sqlalchemy.orm import Session


def validate_task_ownership(
    session: Session,
    *,
    task_id: UUID,
    analysis_run_id: UUID,
    project_id: UUID,
) -> TaskOwnership:
    """校验消息声称的任务/运行/项目与数据库权威一致；不一致抛 TaskOwnershipError。

    返回经 DB 确认的 TaskOwnership（字段来自数据库，非消息），供 Worker 后续安全使用。
    """
    task = session.get(AnalysisTaskModel, task_id)
    if task is None:
        # 任务不存在属真实错误（非归属不一致），用 NotFoundError 区分。
        raise NotFoundError(f"分析任务不存在：{task_id}")

    # 任务确属消息声称的运行。
    if task.analysis_run_id != analysis_run_id:
        raise TaskOwnershipError(
            f"任务 {task_id} 不属于运行 {analysis_run_id}（实际属于 {task.analysis_run_id}）"
        )
    # 任务确属消息声称的项目。
    if task.project_id != project_id:
        raise TaskOwnershipError(
            f"任务 {task_id} 不属于项目 {project_id}（实际属于 {task.project_id}）"
        )

    # 运行存在且与任务同属一项目（运行-项目一致性）。
    run = session.get(AnalysisRunModel, task.analysis_run_id)
    if run is None:
        raise TaskOwnershipError(f"任务 {task_id} 引用的运行 {task.analysis_run_id} 不存在")
    if run.project_id != project_id:
        raise TaskOwnershipError(
            f"运行 {task.analysis_run_id} 不属于项目 {project_id}（实际属于 {run.project_id}）"
        )

    return TaskOwnership(
        task_id=task.id,
        analysis_run_id=task.analysis_run_id,
        project_id=task.project_id,
    )
