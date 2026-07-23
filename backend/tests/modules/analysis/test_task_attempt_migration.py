"""TaskAttempt 迁移测试（D-005 独立验证）。

验证执行尝试表结构、无身份字段，每次重试新增记录且不覆盖旧尝试（attempt_number
任务内唯一自增）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


def test_task_attempts_table_structure(engine) -> None:
    """task_attempts 表存在且含核心列，无身份字段。"""
    inspector = inspect(engine)
    assert "task_attempts" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("task_attempts")}
    required = {
        "id",
        "analysis_task_id",
        "attempt_number",
        "status",
        "started_at",
        "finished_at",
        "error_code",
    }
    assert required <= cols
    forbidden = {"organization_id", "user_id", "created_by", "reviewed_by"}
    assert not (forbidden & cols)


def _seed_task(session) -> tuple[object, object]:
    """建项目+运行+任务，返回 (project_id, task_id)。"""
    from tender_insight.modules.analysis.infrastructure.models import (
        AnalysisRunModel,
        AnalysisTaskModel,
    )
    from tender_insight.modules.project.infrastructure.models import ProjectModel

    project_id = uuid4()
    run_id = uuid4()
    task_id = uuid4()
    session.execute(
        ProjectModel.__table__.insert().values(
            id=project_id, name="p", region="成都", industry="房建",
            project_type="施工", lifecycle_state="ACTIVE", version=1,
        )
    )
    session.execute(
        AnalysisRunModel.__table__.insert().values(
            id=run_id, project_id=project_id, status="QUEUED",
            input_fingerprint="a" * 64,
        )
    )
    session.execute(
        AnalysisTaskModel.__table__.insert().values(
            id=task_id, analysis_run_id=run_id, project_id=project_id,
            task_type="parse", status="PENDING", idempotency_key="k1",
        )
    )
    session.commit()
    return project_id, task_id


def _insert_attempt(
    session, *, task_id, attempt_number, status, error_code=None
) -> None:
    from tender_insight.modules.analysis.infrastructure.models import TaskAttemptModel

    started = datetime(2026, 7, 23, tzinfo=UTC) + timedelta(minutes=attempt_number)
    session.execute(
        TaskAttemptModel.__table__.insert().values(
            id=uuid4(),
            analysis_task_id=task_id,
            attempt_number=attempt_number,
            status=status,
            started_at=started,
            finished_at=started + timedelta(seconds=30) if status != "RUNNING" else None,
            error_code=error_code,
        )
    )
    session.commit()


def test_retry_adds_new_attempt_without_overwriting(session_factory) -> None:
    """每次重试新增记录，旧尝试保留且 attempt_number 自增。"""
    from tender_insight.modules.analysis.infrastructure.models import TaskAttemptModel

    session = session_factory()
    try:
        _, task_id = _seed_task(session)
        _insert_attempt(session, task_id=task_id, attempt_number=1, status="FAILED", error_code="NETWORK")
        _insert_attempt(session, task_id=task_id, attempt_number=2, status="SUCCEEDED")

        rows = (
            session.execute(
                TaskAttemptModel.__table__.select()
                .where(TaskAttemptModel.__table__.c.analysis_task_id == task_id)
                .order_by(TaskAttemptModel.__table__.c.attempt_number)
            )
            .all()
        )
        # 两次尝试都保留，旧失败记录未被覆盖。
        assert [r.attempt_number for r in rows] == [1, 2]
        assert rows[0].status == "FAILED"
        assert rows[0].error_code == "NETWORK"
        assert rows[1].status == "SUCCEEDED"
        assert rows[1].error_code is None
    finally:
        session.close()


def test_attempt_number_unique_per_task(session_factory) -> None:
    """同一任务内 attempt_number 唯一（不能重复写入同序号）。"""
    session = session_factory()
    try:
        _, task_id = _seed_task(session)
        _insert_attempt(session, task_id=task_id, attempt_number=1, status="FAILED")
        with pytest.raises(IntegrityError):
            _insert_attempt(session, task_id=task_id, attempt_number=1, status="SUCCEEDED")
    finally:
        session.close()


def test_attempt_must_reference_task(session_factory) -> None:
    """尝试必须关联任务：analysis_task_id 外键引用 analysis_tasks。"""
    from tender_insight.modules.analysis.infrastructure.models import TaskAttemptModel

    session = session_factory()
    try:
        with pytest.raises(IntegrityError):
            session.execute(
                TaskAttemptModel.__table__.insert().values(
                    id=uuid4(),
                    analysis_task_id=uuid4(),  # 不存在的任务
                    attempt_number=1,
                    status="RUNNING",
                    started_at=datetime(2026, 7, 23, tzinfo=UTC),
                )
            )
            session.commit()
    finally:
        session.close()


def test_attempt_number_independent_across_tasks(session_factory) -> None:
    """不同任务可各自从 1 开始编号。"""
    from tender_insight.modules.analysis.infrastructure.models import (
        AnalysisTaskModel,
    )

    session = session_factory()
    try:
        _, task_a = _seed_task(session)
        # 再建一个任务（同运行内，不同幂等键）。
        from tender_insight.modules.analysis.infrastructure.models import (
            AnalysisRunModel,
        )
        from tender_insight.modules.project.infrastructure.models import ProjectModel

        project_id = session.execute(
            ProjectModel.__table__.select()
        ).first().id
        run_id = session.execute(
            AnalysisRunModel.__table__.select()
        ).first().id
        task_b = uuid4()
        session.execute(
            AnalysisTaskModel.__table__.insert().values(
                id=task_b, analysis_run_id=run_id, project_id=project_id,
                task_type="ocr", status="PENDING", idempotency_key="k2",
            )
        )
        session.commit()
        _insert_attempt(session, task_id=task_a, attempt_number=1, status="SUCCEEDED")
        _insert_attempt(session, task_id=task_b, attempt_number=1, status="SUCCEEDED")
    finally:
        session.close()
