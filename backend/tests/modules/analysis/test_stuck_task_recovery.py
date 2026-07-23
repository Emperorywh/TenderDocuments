"""卡死任务恢复测试（D-018 独立验证）。

验证强制终止 Worker（心跳过期）后任务按策略恢复：标记卡死尝试 FAILED（保留不覆盖），
任务转 RETRY_SCHEDULED（可重试）或 FAILED（超限）；重投递后重新领取生成新尝试，
旧失败记录保留（SPEC.md 第 11.2 节）。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from tender_insight.modules.analysis.application import RecoveryAction
from tender_insight.modules.analysis.infrastructure.models import (
    AnalysisTaskModel,
    TaskAttemptModel,
)
from tender_insight.modules.analysis.infrastructure.stuck_task_recovery import (
    recover_stuck_task,
)
from tender_insight.modules.analysis.infrastructure.task_claim import (
    claim_task_for_execution,
)
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.states import AnalysisTaskStatus

_NOW = datetime(2026, 7, 23, 10, 30, tzinfo=UTC)


def _seed_project(session) -> object:
    from tender_insight.modules.project.infrastructure.models import ProjectModel

    project_id = uuid4()
    session.execute(
        ProjectModel.__table__.insert().values(
            id=project_id,
            name="p",
            region="成都",
            industry="房建",
            project_type="施工",
            lifecycle_state="ACTIVE",
            version=1,
        )
    )
    session.commit()
    return project_id


def _seed_run(session, project_id) -> object:
    from tender_insight.modules.analysis.infrastructure.models import AnalysisRunModel

    run_id = uuid4()
    session.execute(
        AnalysisRunModel.__table__.insert().values(
            id=run_id,
            project_id=project_id,
            status="QUEUED",
            input_fingerprint="fp-1",
        )
    )
    session.commit()
    return run_id


def _seed_task(session, *, run_id, project_id, status=AnalysisTaskStatus.RUNNING) -> object:
    tid = uuid4()
    session.execute(
        AnalysisTaskModel.__table__.insert().values(
            id=tid,
            analysis_run_id=run_id,
            project_id=project_id,
            task_type="parse",
            status=status.value,
            idempotency_key=f"key-{tid}",
        )
    )
    session.commit()
    return tid


def _insert_attempt(
    session,
    *,
    task_id,
    attempt_number,
    status="RUNNING",
    started_at=_NOW,
    error_code=None,
) -> None:
    session.execute(
        TaskAttemptModel.__table__.insert().values(
            id=uuid4(),
            analysis_task_id=task_id,
            attempt_number=attempt_number,
            status=status,
            started_at=started_at,
            error_code=error_code,
        )
    )
    session.commit()


def test_recover_marks_attempt_failed_and_schedules_retry(db_session: Session) -> None:
    """核心验证：卡死任务恢复——尝试标记 FAILED，任务转 RETRY_SCHEDULED。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    _insert_attempt(db_session, task_id=task_id, attempt_number=1, status="RUNNING")

    outcome = recover_stuck_task(db_session, task_id, now=_NOW, max_retries=3)
    db_session.commit()

    assert outcome is not None
    assert outcome.action is RecoveryAction.SCHEDULED_RETRY
    assert outcome.failed_attempt_number == 1
    assert db_session.get(AnalysisTaskModel, task_id).status == AnalysisTaskStatus.RETRY_SCHEDULED.value
    attempt = db_session.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).one()
    assert attempt.status == "FAILED"
    assert attempt.error_code == "HEARTBEAT_TIMEOUT"
    assert attempt.finished_at is not None


def test_recover_fails_task_when_retries_exhausted(db_session: Session) -> None:
    """超过最大重试：任务转终态 FAILED。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    # 已有 3 次失败尝试 + 当前 RUNNING 第 4 次（总 4 次，retries_used=3）。
    for n in range(1, 4):
        _insert_attempt(
            db_session, task_id=task_id, attempt_number=n, status="FAILED", error_code="HEARTBEAT_TIMEOUT"
        )
    _insert_attempt(db_session, task_id=task_id, attempt_number=4, status="RUNNING")

    outcome = recover_stuck_task(db_session, task_id, now=_NOW, max_retries=3)
    db_session.commit()

    assert outcome is not None
    assert outcome.action is RecoveryAction.FAILED
    assert db_session.get(AnalysisTaskModel, task_id).status == AnalysisTaskStatus.FAILED.value
    # 第 4 次尝试也被标记 FAILED。
    assert (
        db_session.query(TaskAttemptModel)
        .filter_by(analysis_task_id=task_id, attempt_number=4)
        .one()
        .status
        == "FAILED"
    )


def test_recover_preserves_old_attempt_on_reclaim(db_session: Session) -> None:
    """SPEC 11.2：恢复后重投递并重新领取，生成新尝试；旧失败记录保留不覆盖。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    _insert_attempt(db_session, task_id=task_id, attempt_number=1, status="RUNNING")

    # 1) 恢复：尝试 1 FAILED，任务 RETRY_SCHEDULED。
    recover_stuck_task(db_session, task_id, now=_NOW, max_retries=3)
    db_session.commit()

    # 2) 重投递（RETRY_SCHEDULED→DISPATCHED，D-020 职责，此处直接置位模拟）。
    db_session.execute(
        AnalysisTaskModel.__table__.update()
        .where(AnalysisTaskModel.id == task_id)
        .values(status=AnalysisTaskStatus.DISPATCHED.value)
    )
    db_session.commit()

    # 3) 重新领取（D-013）：生成新尝试 2，任务 RUNNING。
    claimed = claim_task_for_execution(db_session, task_id, now=_NOW)
    db_session.commit()

    assert claimed is not None
    assert claimed.attempt_number == 2
    attempts = (
        db_session.query(TaskAttemptModel)
        .filter_by(analysis_task_id=task_id)
        .order_by(TaskAttemptModel.attempt_number)
        .all()
    )
    # 旧尝试 1 仍 FAILED（保留不覆盖）；新尝试 2 RUNNING。
    assert [a.attempt_number for a in attempts] == [1, 2]
    assert attempts[0].status == "FAILED"
    assert attempts[1].status == "RUNNING"


def test_recover_returns_none_for_non_running(db_session: Session) -> None:
    """非 RUNNING（已恢复/终态）不重复恢复，返回 None。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(
        db_session, run_id=run_id, project_id=project_id, status=AnalysisTaskStatus.SUCCEEDED
    )

    assert recover_stuck_task(db_session, task_id, now=_NOW, max_retries=3) is None


def test_recover_idempotent(db_session: Session) -> None:
    """重复恢复幂等：第一次恢复后任务离开 RUNNING，第二次返回 None。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    _insert_attempt(db_session, task_id=task_id, attempt_number=1, status="RUNNING")

    first = recover_stuck_task(db_session, task_id, now=_NOW, max_retries=3)
    db_session.commit()
    second = recover_stuck_task(db_session, task_id, now=_NOW, max_retries=3)
    db_session.commit()

    assert first is not None
    assert second is None


def test_recover_raises_not_found_for_unknown_task(db_session: Session) -> None:
    """未知任务抛 NotFoundError。"""
    with pytest.raises(NotFoundError):
        recover_stuck_task(db_session, uuid4(), now=_NOW, max_retries=3)


def test_recover_custom_error_code(db_session: Session) -> None:
    """恢复支持自定义错误码（D-019 错误分类）。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    _insert_attempt(db_session, task_id=task_id, attempt_number=1, status="RUNNING")

    recover_stuck_task(
        db_session, task_id, now=_NOW, max_retries=3, error_code="WORKER_CRASHED"
    )
    db_session.commit()

    attempt = db_session.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).one()
    assert attempt.error_code == "WORKER_CRASHED"
