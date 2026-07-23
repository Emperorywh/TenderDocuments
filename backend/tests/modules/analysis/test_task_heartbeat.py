"""任务心跳测试（D-016 独立验证）。

验证运行任务在设定间隔内刷新数据库心跳（heartbeat_at）：心跳写在当前 RUNNING 尝试上，
周期刷新使时间戳前进；无 RUNNING 尝试时返回 False。卡死任务扫描（D-017）据此识别
过期心跳。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from tender_insight.modules.analysis.infrastructure.models import (
    AnalysisTaskModel,
    TaskAttemptModel,
)
from tender_insight.modules.analysis.infrastructure.task_heartbeat import (
    refresh_heartbeat,
)


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


def _seed_task(session, *, run_id, project_id) -> object:
    tid = uuid4()
    session.execute(
        AnalysisTaskModel.__table__.insert().values(
            id=tid,
            analysis_run_id=run_id,
            project_id=project_id,
            task_type="parse",
            status="RUNNING",
            idempotency_key=f"key-{tid}",
        )
    )
    session.commit()
    return tid


def _insert_attempt(
    session,
    *,
    task_id,
    attempt_number=1,
    status="RUNNING",
    started_at=None,
) -> None:
    session.execute(
        TaskAttemptModel.__table__.insert().values(
            id=uuid4(),
            analysis_task_id=task_id,
            attempt_number=attempt_number,
            status=status,
            started_at=started_at or datetime(2026, 7, 23, 10, 0, tzinfo=UTC),
        )
    )
    session.commit()


def test_heartbeat_column_exists_and_nullable(engine) -> None:
    """迁移新增 heartbeat_at 列，可为空（新尝试初始无心跳）。"""
    inspector = inspect(engine)
    cols = {c["name"]: c for c in inspector.get_columns("task_attempts")}
    assert "heartbeat_at" in cols
    assert cols["heartbeat_at"]["nullable"] is True


def test_refresh_heartbeat_updates_running_attempt(db_session: Session) -> None:
    """刷新心跳：当前 RUNNING 尝试的 heartbeat_at 置为 now，返回 True。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    _insert_attempt(db_session, task_id=task_id, status="RUNNING")
    now = datetime(2026, 7, 23, 10, 5, tzinfo=UTC)

    result = refresh_heartbeat(db_session, task_id, now=now)
    db_session.commit()

    assert result is True
    attempt = db_session.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).one()
    # SQLite 不保留时区，按 UTC 规范化比较（生产 PG 保留时区）。
    hb = attempt.heartbeat_at
    if hb.tzinfo is None:
        hb = hb.replace(tzinfo=UTC)
    assert hb == now


def test_refresh_heartbeat_returns_false_when_no_running_attempt(db_session: Session) -> None:
    """无 RUNNING 尝试（任务未运行/已终态）时返回 False，不修改任何尝试。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    _insert_attempt(db_session, task_id=task_id, status="SUCCEEDED")
    now = datetime(2026, 7, 23, 10, 5, tzinfo=UTC)

    result = refresh_heartbeat(db_session, task_id, now=now)
    db_session.commit()

    assert result is False
    attempt = db_session.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).one()
    assert attempt.heartbeat_at is None


def test_refresh_heartbeat_advances_on_periodic_refresh(db_session: Session) -> None:
    """运行任务在设定间隔内多次刷新心跳，heartbeat_at 随之前进（核心验证）。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    _insert_attempt(db_session, task_id=task_id, status="RUNNING")

    t1 = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
    t2 = t1 + timedelta(seconds=15)
    t3 = t2 + timedelta(seconds=15)

    refresh_heartbeat(db_session, task_id, now=t1)
    db_session.commit()
    refresh_heartbeat(db_session, task_id, now=t2)
    db_session.commit()
    refresh_heartbeat(db_session, task_id, now=t3)
    db_session.commit()

    attempt = db_session.query(TaskAttemptModel).filter_by(analysis_task_id=task_id).one()
    hb = attempt.heartbeat_at
    if hb.tzinfo is None:
        hb = hb.replace(tzinfo=UTC)
    # 心跳为最后一次刷新时间。
    assert hb == t3


def test_refresh_heartbeat_targets_latest_running_attempt(db_session: Session) -> None:
    """多次尝试中，刷新作用于最新 RUNNING 尝试（旧已完成尝试不动）。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    task_id = _seed_task(db_session, run_id=run_id, project_id=project_id)
    _insert_attempt(
        db_session,
        task_id=task_id,
        attempt_number=1,
        status="FAILED",
        started_at=datetime(2026, 7, 23, 9, 0, tzinfo=UTC),
    )
    _insert_attempt(
        db_session,
        task_id=task_id,
        attempt_number=2,
        status="RUNNING",
        started_at=datetime(2026, 7, 23, 10, 0, tzinfo=UTC),
    )
    now = datetime(2026, 7, 23, 10, 5, tzinfo=UTC)

    result = refresh_heartbeat(db_session, task_id, now=now)
    db_session.commit()

    assert result is True
    attempts = (
        db_session.query(TaskAttemptModel)
        .filter_by(analysis_task_id=task_id)
        .order_by(TaskAttemptModel.attempt_number)
        .all()
    )
    # 旧失败尝试无心跳；新 RUNNING 尝试刷新心跳。
    assert attempts[0].heartbeat_at is None
    assert attempts[1].heartbeat_at is not None


def test_refresh_heartbeat_unknown_task_returns_false(db_session: Session) -> None:
    """未知任务无 RUNNING 尝试，返回 False（不抛错，心跳周期容错）。"""
    result = refresh_heartbeat(db_session, uuid4(), now=datetime(2026, 7, 23, 10, 5, tzinfo=UTC))
    assert result is False
