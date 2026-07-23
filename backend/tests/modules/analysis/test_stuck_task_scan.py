"""卡死任务扫描测试（D-017 独立验证）。

验证超时任务识别：心跳过期（最近活动早于阈值）的 RUNNING 任务被识别；正常心跳
（最近活动新于阈值）不被误判；回退 started_at 覆盖领取后未刷新心跳即崩溃的情形。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from tender_insight.modules.analysis.infrastructure.models import (
    AnalysisRunModel,
    AnalysisTaskModel,
    TaskAttemptModel,
)
from tender_insight.modules.analysis.infrastructure.stuck_task_scan import (
    find_stuck_tasks,
)

_TIMEOUT = 60.0  # 60 秒心跳超时。
_BASE = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)


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


def _seed_running_task_with_attempt(
    session,
    *,
    run_id,
    project_id,
    started_at,
    heartbeat_at=None,
    task_status="RUNNING",
) -> object:
    """建 RUNNING 任务 + RUNNING 尝试（started_at/heartbeat_at 可控）。"""
    tid = uuid4()
    session.execute(
        AnalysisTaskModel.__table__.insert().values(
            id=tid,
            analysis_run_id=run_id,
            project_id=project_id,
            task_type="parse",
            status=task_status,
            idempotency_key=f"key-{tid}",
        )
    )
    session.execute(
        TaskAttemptModel.__table__.insert().values(
            id=uuid4(),
            analysis_task_id=tid,
            attempt_number=1,
            status="RUNNING",
            started_at=started_at,
            heartbeat_at=heartbeat_at,
        )
    )
    session.commit()
    return tid


def test_scan_identifies_stale_heartbeat(db_session: Session) -> None:
    """核心验证：心跳过期的 RUNNING 任务被识别。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    now = _BASE + timedelta(seconds=200)
    # 心跳在 120s 前，超过 60s 阈值 → 卡死。
    _seed_running_task_with_attempt(
        db_session,
        run_id=run_id,
        project_id=project_id,
        started_at=_BASE,
        heartbeat_at=now - timedelta(seconds=120),
    )

    stuck = find_stuck_tasks(db_session, now=now, heartbeat_timeout_seconds=_TIMEOUT)

    assert len(stuck) == 1
    assert stuck[0].attempt_number == 1


def test_scan_does_not_misjudge_fresh_heartbeat(db_session: Session) -> None:
    """核心验证：正常心跳（新于阈值）不被误判为卡死。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    now = _BASE + timedelta(seconds=200)
    # 心跳在 10s 前，未超 60s 阈值 → 正常。
    _seed_running_task_with_attempt(
        db_session,
        run_id=run_id,
        project_id=project_id,
        started_at=_BASE,
        heartbeat_at=now - timedelta(seconds=10),
    )

    assert find_stuck_tasks(db_session, now=now, heartbeat_timeout_seconds=_TIMEOUT) == []


def test_scan_falls_back_to_started_at_when_no_heartbeat(db_session: Session) -> None:
    """无心跳（领取后未刷新即崩溃）回退 started_at：过期则识别。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    now = _BASE + timedelta(seconds=200)
    # 无 heartbeat_at；started_at 在 200s 前，超阈值 → 卡死。
    _seed_running_task_with_attempt(
        db_session,
        run_id=run_id,
        project_id=project_id,
        started_at=_BASE,
        heartbeat_at=None,
    )

    stuck = find_stuck_tasks(db_session, now=now, heartbeat_timeout_seconds=_TIMEOUT)
    assert len(stuck) == 1


def test_scan_fresh_started_at_not_stuck(db_session: Session) -> None:
    """无心跳但 started_at 新近（刚领取）不被误判。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    now = _BASE + timedelta(seconds=200)
    _seed_running_task_with_attempt(
        db_session,
        run_id=run_id,
        project_id=project_id,
        started_at=now - timedelta(seconds=5),  # 刚领取
        heartbeat_at=None,
    )

    assert find_stuck_tasks(db_session, now=now, heartbeat_timeout_seconds=_TIMEOUT) == []


def test_scan_ignores_non_running_attempts(db_session: Session) -> None:
    """已完成的尝试（SUCCEEDED/FAILED）即使活动时间旧也不被识别为卡死。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    now = _BASE + timedelta(seconds=200)
    tid = uuid4()
    session = db_session
    session.execute(
        AnalysisTaskModel.__table__.insert().values(
            id=tid,
            analysis_run_id=run_id,
            project_id=project_id,
            task_type="parse",
            status="SUCCEEDED",
            idempotency_key=f"key-{tid}",
        )
    )
    session.execute(
        TaskAttemptModel.__table__.insert().values(
            id=uuid4(),
            analysis_task_id=tid,
            attempt_number=1,
            status="SUCCEEDED",
            started_at=_BASE,
            heartbeat_at=_BASE,  # 旧，但已完成
        )
    )
    session.commit()

    assert find_stuck_tasks(db_session, now=now, heartbeat_timeout_seconds=_TIMEOUT) == []


def test_scan_returns_context_fields(db_session: Session) -> None:
    """返回的 StuckTask 含稳定归属与判定依据（供 D-018 恢复）。"""
    project_id = _seed_project(db_session)
    run_id = _seed_run(db_session, project_id)
    now = _BASE + timedelta(seconds=200)
    hb = now - timedelta(seconds=120)
    task_id = _seed_running_task_with_attempt(
        db_session,
        run_id=run_id,
        project_id=project_id,
        started_at=_BASE,
        heartbeat_at=hb,
    )

    stuck = find_stuck_tasks(db_session, now=now, heartbeat_timeout_seconds=_TIMEOUT)
    assert len(stuck) == 1
    item = stuck[0]
    assert item.task_id == task_id
    assert item.analysis_run_id == run_id
    assert item.project_id == project_id
    # last_activity 取心跳值（已刷新过）。
    expected = hb.replace(tzinfo=None) if hb.tzinfo else hb
    assert item.last_activity.replace(tzinfo=None) == expected


def test_scan_empty_when_no_tasks(db_session: Session) -> None:
    """无任务时扫描返回空。"""
    now = _BASE + timedelta(seconds=200)
    assert find_stuck_tasks(db_session, now=now, heartbeat_timeout_seconds=_TIMEOUT) == []
