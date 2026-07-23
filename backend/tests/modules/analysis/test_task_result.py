"""任务幂等结果提交测试（D-015 独立验证）。

验证守卫式原子结果提交：RUNNING→SUCCEEDED/FAILED 只发生一次；重复消息（已终态）的
再次提交为幂等空操作（返回 False），不重复标记尝试、不产生重复正式结果。
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from tender_insight.modules.analysis.infrastructure.models import (
    AnalysisTaskModel,
    TaskAttemptModel,
)
from tender_insight.modules.analysis.infrastructure.task_result import (
    submit_task_result,
)
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.states import AnalysisTaskStatus

_NOW = datetime(2026, 7, 23, 10, 30, tzinfo=UTC)
_FINISH = datetime(2026, 7, 23, 10, 35, tzinfo=UTC)


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


def _seed_attempt(
    session,
    *,
    task_id,
    attempt_number=1,
    status="RUNNING",
    started_at=_NOW,
) -> None:
    session.execute(
        TaskAttemptModel.__table__.insert().values(
            id=uuid4(),
            analysis_task_id=task_id,
            attempt_number=attempt_number,
            status=status,
            started_at=started_at,
        )
    )
    session.commit()


def test_submit_success_transitions_task_and_finishes_attempt(db_session: Session) -> None:
    """成功提交：任务 SUCCEEDED，当前尝试完成（finished_at 设置，无 error_code）。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    _seed_attempt(db_session, task_id=task_id)

    newly = submit_task_result(db_session, task_id, succeeded=True, now=_FINISH)
    db_session.commit()

    assert newly is True
    assert db_session.get(AnalysisTaskModel, task_id).status == AnalysisTaskStatus.SUCCEEDED.value
    attempt = db_session.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).one()
    assert attempt.status == "SUCCEEDED"
    assert attempt.finished_at is not None
    assert attempt.error_code is None


def test_submit_failure_records_error_code(db_session: Session) -> None:
    """失败提交：任务 FAILED，尝试记录稳定错误码。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    _seed_attempt(db_session, task_id=task_id)

    newly = submit_task_result(
        db_session, task_id, succeeded=False, error_code="CORRUPT_FILE", now=_FINISH
    )
    db_session.commit()

    assert newly is True
    assert db_session.get(AnalysisTaskModel, task_id).status == AnalysisTaskStatus.FAILED.value
    attempt = db_session.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).one()
    assert attempt.status == "FAILED"
    assert attempt.error_code == "CORRUPT_FILE"


def test_duplicate_submit_is_idempotent_noop(db_session: Session) -> None:
    """核心验证：重复消息不产生重复正式结果——第二次提交为幂等空操作。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    _seed_attempt(db_session, task_id=task_id)

    first = submit_task_result(db_session, task_id, succeeded=True, now=_FINISH)
    db_session.commit()
    second = submit_task_result(db_session, task_id, succeeded=True, now=_FINISH)
    db_session.commit()

    assert first is True
    assert second is False
    # 任务仅一次 SUCCEEDED；尝试仅一次完成。
    assert db_session.get(AnalysisTaskModel, task_id).status == AnalysisTaskStatus.SUCCEEDED.value
    attempts = db_session.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).all()
    assert len(attempts) == 1
    assert attempts[0].status == "SUCCEEDED"


@pytest.mark.parametrize(
    "status",
    [
        AnalysisTaskStatus.PENDING,
        AnalysisTaskStatus.DISPATCHED,
        AnalysisTaskStatus.SUCCEEDED,
        AnalysisTaskStatus.FAILED,
        AnalysisTaskStatus.CANCELLED,
        AnalysisTaskStatus.RETRY_SCHEDULED,
    ],
)
def test_submit_returns_false_for_non_running(
    db_session: Session, status: AnalysisTaskStatus
) -> None:
    """非 RUNNING 状态提交结果为空操作（未执行/已终态/待重试），返回 False。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id, status=status)

    assert submit_task_result(db_session, task_id, succeeded=True, now=_FINISH) is False
    # 状态不变。
    assert db_session.get(AnalysisTaskModel, task_id).status == status.value


def test_submit_raises_not_found_for_unknown_task(db_session: Session) -> None:
    """未知任务抛 NotFoundError。"""
    with pytest.raises(NotFoundError):
        submit_task_result(db_session, uuid4(), succeeded=True, now=_FINISH)


def test_concurrent_submit_only_one_wins(session_factory) -> None:
    """并发提交同一 RUNNING 任务，只一个成功（任务只转换一次，不重复结果）。"""
    setup = session_factory()
    try:
        project_id = _seed_project(setup)
        run_id = _seed_run(setup, project_id)
        task_id = _seed_task(setup, run_id=run_id, project_id=project_id)
        _seed_attempt(setup, task_id=task_id)
    finally:
        setup.close()

    session_a = session_factory()
    session_b = session_factory()
    try:
        newly_a = submit_task_result(session_a, task_id, succeeded=True, now=_FINISH)
        session_a.commit()

        newly_b = submit_task_result(session_b, task_id, succeeded=True, now=_FINISH)
        session_b.commit()
    finally:
        session_a.close()
        session_b.close()

    assert newly_a is True
    assert newly_b is False

    verify = session_factory()
    try:
        assert verify.get(AnalysisTaskModel, task_id).status == AnalysisTaskStatus.SUCCEEDED.value
        attempt = verify.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).one()
        assert attempt.status == "SUCCEEDED"
    finally:
        verify.close()
