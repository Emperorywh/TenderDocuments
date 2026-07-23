"""Worker 任务归属校验测试（D-014 独立验证）。

验证消息声称的 task/run/project 与数据库权威交叉校验：一致时返回 DB 确认的归属；
任一不一致（伪造或不匹配）抛 TaskOwnershipError 拒绝执行。Worker 不信任消息中的
孤立 ID（SPEC.md 第 4.3 节）。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from tender_insight.modules.analysis.application import TaskOwnership
from tender_insight.modules.analysis.domain.exceptions import TaskOwnershipError
from tender_insight.modules.analysis.infrastructure.models import (
    AnalysisRunModel,
    AnalysisTaskModel,
)
from tender_insight.modules.analysis.infrastructure.task_ownership import (
    validate_task_ownership,
)
from tender_insight.shared.errors import NotFoundError


def _seed_project(session, *, project_id=None, name="p") -> object:
    from tender_insight.modules.project.infrastructure.models import ProjectModel

    pid = project_id or uuid4()
    session.execute(
        ProjectModel.__table__.insert().values(
            id=pid,
            name=name,
            region="成都",
            industry="房建",
            project_type="施工",
            lifecycle_state="ACTIVE",
            version=1,
        )
    )
    session.commit()
    return pid


def _seed_run(session, *, project_id, run_id=None, status="QUEUED") -> object:
    rid = run_id or uuid4()
    session.execute(
        AnalysisRunModel.__table__.insert().values(
            id=rid,
            project_id=project_id,
            status=status,
            input_fingerprint=f"fp-{rid}",
        )
    )
    session.commit()
    return rid


def _seed_task(
    session,
    *,
    run_id,
    project_id,
    task_id=None,
    status="DISPATCHED",
) -> object:
    tid = task_id or uuid4()
    session.execute(
        AnalysisTaskModel.__table__.insert().values(
            id=tid,
            analysis_run_id=run_id,
            project_id=project_id,
            task_type="parse",
            status=status,
            idempotency_key=f"key-{tid}",
        )
    )
    session.commit()
    return tid


def test_validate_consistent_ids_returns_db_ownership(db_session: Session) -> None:
    """一致消息：返回经 DB 确认的归属（字段来自数据库）。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id=project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)

    ownership = validate_task_ownership(
        db_session, task_id=task_id, analysis_run_id=run_id, project_id=project_id
    )

    assert isinstance(ownership, TaskOwnership)
    assert ownership.task_id == task_id
    assert ownership.analysis_run_id == run_id
    assert ownership.project_id == project_id


def test_validate_rejects_wrong_run_id(db_session: Session) -> None:
    """伪造：消息声称的运行不是任务所属运行 → 拒绝执行。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id=project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    forged_run = uuid4()

    with pytest.raises(TaskOwnershipError):
        validate_task_ownership(
            db_session, task_id=task_id, analysis_run_id=forged_run, project_id=project_id
        )


def test_validate_rejects_wrong_project_id(db_session: Session) -> None:
    """伪造：消息声称的项目不是任务所属项目 → 拒绝执行。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id=project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    forged_project = _seed_project(db_session, name="other")

    with pytest.raises(TaskOwnershipError):
        validate_task_ownership(
            db_session,
            task_id=task_id,
            analysis_run_id=run_id,
            project_id=forged_project,
        )


def test_validate_rejects_run_project_mismatch(db_session: Session) -> None:
    """运行与任务不同属一项目（DB 不一致）→ 拒绝执行。

    任务声称属于 P1，但其运行属于 P2：校验 run.project_id != 声称 project_id 时拒绝。
    """
    project_p1 = _seed_project(db_session, name="p1")
    project_p2 = _seed_project(db_session, name="p2")
    run_of_p2 = _seed_run(db_session, project_id=project_p2)
    # 异常数据：任务 project_id=P1 但挂在 P2 的运行下（模拟数据不一致/伪造）。
    task_id = _seed_task(db_session, run_id=run_of_p2, project_id=project_p1)

    with pytest.raises(TaskOwnershipError):
        validate_task_ownership(
            db_session,
            task_id=task_id,
            analysis_run_id=run_of_p2,
            project_id=project_p1,
        )


def test_validate_raises_not_found_for_unknown_task(db_session: Session) -> None:
    """未知任务抛 NotFoundError（与归属不一致区分）。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id=project_id)

    with pytest.raises(NotFoundError):
        validate_task_ownership(
            db_session,
            task_id=uuid4(),
            analysis_run_id=run_id,
            project_id=project_id,
        )


def test_task_ownership_error_has_stable_code() -> None:
    """TaskOwnershipError 携带稳定错误码（不靠文案判断）。"""
    assert TaskOwnershipError.code == "TASK_OWNERSHIP_MISMATCH"
    assert TaskOwnershipError.http_status == 422
