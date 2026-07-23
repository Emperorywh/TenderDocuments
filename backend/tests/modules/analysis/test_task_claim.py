"""Worker 任务原子领取测试（D-013 独立验证）。

验证守卫式原子领取：同一消息并发消费只获得一个执行权（DISPATCHED→RUNNING 守卫式
UPDATE，仅一个消费者成功）；领取成功新建 TaskAttempt；未获得执行权返回 None 且不
新建尝试；未知任务抛 NotFoundError。

守卫式 UPDATE ... WHERE status='DISPATCHED' 在 PostgreSQL（行级锁串行化）与 SQLite
（串行写）上均正确保证“只一个消费者成功”，故并发排他可在本机 SQLite 上直接验证
（无需 D-009 那样的 PG 方言编译旁证）。
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
from tender_insight.modules.analysis.infrastructure.task_claim import (
    claim_task_for_execution,
)
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.states import AnalysisTaskStatus

_NOW = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


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


def _seed_task(
    session,
    *,
    run_id,
    project_id,
    status: AnalysisTaskStatus = AnalysisTaskStatus.DISPATCHED,
    task_id=None,
) -> object:
    tid = task_id or uuid4()
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


def test_claim_dispatched_task_returns_execution_context(db_session: Session) -> None:
    """DISPATCHED 任务领取成功：返回执行上下文，任务转 RUNNING。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)

    claimed = claim_task_for_execution(db_session, task_id, now=_NOW)
    db_session.commit()

    assert claimed is not None
    assert claimed.task_id == task_id
    assert claimed.analysis_run_id == run_id
    assert claimed.project_id == project_id
    assert claimed.task_type == "parse"
    assert claimed.attempt_number == 1
    task = db_session.get(AnalysisTaskModel, task_id)
    assert task.status == AnalysisTaskStatus.RUNNING.value


def test_claim_creates_running_attempt_with_started_at(db_session: Session) -> None:
    """领取新建一条 RUNNING 尝试，started_at 为注入时间。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)

    claim_task_for_execution(db_session, task_id, now=_NOW)
    db_session.commit()

    attempts = db_session.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).all()
    assert len(attempts) == 1
    assert attempts[0].attempt_number == 1
    assert attempts[0].status == "RUNNING"
    # SQLite 不保留时区（DateTime(timezone=True) 在 SQLite 回读为 naive），按 UTC 还原比较；
    # 生产 PostgreSQL 的 timestamptz 保留时区，此处规范化不影响正确性。
    started = attempts[0].started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    assert started == _NOW
    assert attempts[0].finished_at is None


def test_claim_returns_none_when_already_running(db_session: Session) -> None:
    """任务已被领取（RUNNING）时，并发消费者领取返回 None（未获执行权）。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)

    first = claim_task_for_execution(db_session, task_id, now=_NOW)
    db_session.commit()
    second = claim_task_for_execution(db_session, task_id, now=_NOW)
    db_session.commit()

    assert first is not None
    assert second is None
    # 仅一条尝试（第二个消费者未新建）。
    assert db_session.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).count() == 1


@pytest.mark.parametrize(
    "status",
    [
        AnalysisTaskStatus.SUCCEEDED,
        AnalysisTaskStatus.FAILED,
        AnalysisTaskStatus.CANCELLED,
        AnalysisTaskStatus.PENDING,
        AnalysisTaskStatus.RETRY_SCHEDULED,
    ],
)
def test_claim_returns_none_for_non_dispatched_statuses(
    db_session: Session, status: AnalysisTaskStatus
) -> None:
    """非 DISPATCHED 状态不可领取（终态/未派发/待重试），返回 None。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id, status=status)

    assert claim_task_for_execution(db_session, task_id, now=_NOW) is None
    assert db_session.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).count() == 0


def test_claim_raises_not_found_for_unknown_task(db_session: Session) -> None:
    """未知任务抛 NotFoundError（消息引用不存在的任务属真实错误，非丢失竞争）。"""
    with pytest.raises(NotFoundError):
        claim_task_for_execution(db_session, uuid4(), now=_NOW)


def test_concurrent_claim_only_one_wins(session_factory) -> None:
    """核心验证：两个并发消费者领取同一 DISPATCHED 任务，只一个获得执行权。

    消费者 A 领取并提交后任务为 RUNNING；消费者 B 的守卫式 UPDATE 不再匹配 DISPATCHED，
    返回 None。仅一条执行尝试被创建。
    """
    setup = session_factory()
    try:
        project_id = _seed_project(setup)
        run_id = _seed_run(setup, project_id)
        task_id = _seed_task(setup, run_id=run_id, project_id=project_id)
    finally:
        setup.close()

    session_a = session_factory()
    session_b = session_factory()
    try:
        claimed_a = claim_task_for_execution(session_a, task_id, now=_NOW)
        session_a.commit()

        claimed_b = claim_task_for_execution(session_b, task_id, now=_NOW)
        session_b.commit()
    finally:
        session_a.close()
        session_b.close()

    assert claimed_a is not None
    assert claimed_b is None

    verify = session_factory()
    try:
        task = verify.get(AnalysisTaskModel, task_id)
        assert task.status == AnalysisTaskStatus.RUNNING.value
        # 仅一个消费者新建了尝试。
        assert verify.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).count() == 1
    finally:
        verify.close()


def test_claim_creates_incrementing_attempt_on_retry(db_session: Session) -> None:
    """重试领取：任务回到 DISPATCHED 后再次领取，attempt_number 自增（不覆盖旧尝试）。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)

    first = claim_task_for_execution(db_session, task_id, now=_NOW)
    db_session.commit()
    assert first.attempt_number == 1

    # 模拟重试：任务经 RETRY_SCHEDULED 重新 DISPATCHED（D-020/D-031 职责，此处直接置位）。
    db_session.execute(
        AnalysisTaskModel.__table__.update()
        .where(AnalysisTaskModel.id == task_id)
        .values(status=AnalysisTaskStatus.DISPATCHED.value)
    )
    db_session.commit()

    second = claim_task_for_execution(db_session, task_id, now=_NOW)
    db_session.commit()
    assert second.attempt_number == 2

    numbers = sorted(
        r.attempt_number
        for r in db_session.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).all()
    )
    assert numbers == [1, 2]


def test_claim_does_not_commit_internally(session_factory) -> None:
    """领取不在内部提交：新会话在提交前查不到 RUNNING 状态与尝试。"""
    setup = session_factory()
    try:
        project_id = _seed_project(setup)
        run_id = _seed_run(setup, project_id)
        task_id = _seed_task(setup, run_id=run_id, project_id=project_id)
    finally:
        setup.close()

    session = session_factory()
    try:
        claim_task_for_execution(session, task_id, now=_NOW)
        # 未提交前，另一会话看不到任务状态变更与尝试。
        other = session_factory()
        try:
            assert (
                other.get(AnalysisTaskModel, task_id).status
                == AnalysisTaskStatus.DISPATCHED.value
            )
            assert other.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).count() == 0
        finally:
            other.close()
        session.commit()
    finally:
        session.close()

    verify = session_factory()
    try:
        assert verify.get(AnalysisTaskModel, task_id).status == AnalysisTaskStatus.RUNNING.value
        assert verify.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).count() == 1
    finally:
        verify.close()
