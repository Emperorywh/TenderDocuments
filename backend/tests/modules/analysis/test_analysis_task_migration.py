"""AnalysisTask 迁移测试（D-004 独立验证）。

验证原子任务表结构正确、无身份字段，任务必须关联运行与项目，幂等键在运行内唯一。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


def test_analysis_tasks_table_structure(engine) -> None:
    """analysis_tasks 表存在且含核心列，无身份字段。"""
    inspector = inspect(engine)
    assert "analysis_tasks" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("analysis_tasks")}
    required = {
        "id",
        "analysis_run_id",
        "project_id",
        "task_type",
        "status",
        "idempotency_key",
    }
    assert required <= cols
    forbidden = {"organization_id", "user_id", "created_by", "reviewed_by"}
    assert not (forbidden & cols)


def _seed_run(session, *, project_id, run_id, fingerprint="a" * 64) -> None:
    from tender_insight.modules.analysis.infrastructure.models import AnalysisRunModel

    session.execute(
        AnalysisRunModel.__table__.insert().values(
            id=run_id,
            project_id=project_id,
            status="QUEUED",
            input_fingerprint=fingerprint,
        )
    )


def _seed_project(session) -> object:
    from tender_insight.modules.project.infrastructure.models import ProjectModel

    project_id = uuid4()
    session.execute(
        ProjectModel.__table__.insert().values(
            id=project_id, name="p", region="成都", industry="房建",
            project_type="施工", lifecycle_state="ACTIVE", version=1,
        )
    )
    session.commit()
    return project_id


def test_task_must_reference_run(session_factory) -> None:
    """任务必须关联运行：analysis_run_id 外键引用 analysis_runs。"""
    from tender_insight.modules.analysis.infrastructure.models import AnalysisTaskModel

    session = session_factory()
    try:
        project_id = _seed_project(session)
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(
                AnalysisTaskModel.__table__.insert().values(
                    id=uuid4(),
                    analysis_run_id=uuid4(),  # 不存在的运行
                    project_id=project_id,
                    task_type="parse",
                    status="PENDING",
                    idempotency_key="k1",
                )
            )
            session.commit()
    finally:
        session.close()


def test_task_must_reference_project(session_factory) -> None:
    """任务必须关联项目：project_id 外键引用 projects。"""
    from tender_insight.modules.analysis.infrastructure.models import AnalysisTaskModel

    session = session_factory()
    try:
        project_id = _seed_project(session)
        run_id = uuid4()
        _seed_run(session, project_id=project_id, run_id=run_id)
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(
                AnalysisTaskModel.__table__.insert().values(
                    id=uuid4(),
                    analysis_run_id=run_id,
                    project_id=uuid4(),  # 不存在的项目
                    task_type="parse",
                    status="PENDING",
                    idempotency_key="k2",
                )
            )
            session.commit()
    finally:
        session.close()


def test_task_associates_run_and_project(session_factory) -> None:
    """任务同时关联运行与项目，可持久化回读。"""
    from tender_insight.modules.analysis.infrastructure.models import AnalysisTaskModel

    session = session_factory()
    try:
        project_id = _seed_project(session)
        run_id = uuid4()
        _seed_run(session, project_id=project_id, run_id=run_id)
        session.commit()

        task_id = uuid4()
        session.execute(
            AnalysisTaskModel.__table__.insert().values(
                id=task_id,
                analysis_run_id=run_id,
                project_id=project_id,
                task_type="ocr",
                status="DISPATCHED",
                idempotency_key="k3",
            )
        )
        session.commit()
        row = session.execute(
            AnalysisTaskModel.__table__.select().where(
                AnalysisTaskModel.__table__.c.id == task_id
            )
        ).one()
        assert row.analysis_run_id == run_id
        assert row.project_id == project_id
        assert row.task_type == "ocr"
        assert row.status == "DISPATCHED"
    finally:
        session.close()


def test_idempotency_key_unique_within_run(session_factory) -> None:
    """同一运行内相同幂等键被拒绝（防重复正式结果）。"""
    from tender_insight.modules.analysis.infrastructure.models import AnalysisTaskModel

    session = session_factory()
    try:
        project_id = _seed_project(session)
        run_id = uuid4()
        _seed_run(session, project_id=project_id, run_id=run_id)
        session.execute(
            AnalysisTaskModel.__table__.insert().values(
                id=uuid4(), analysis_run_id=run_id, project_id=project_id,
                task_type="parse", status="PENDING", idempotency_key="dup",
            )
        )
        session.commit()
        with pytest.raises(IntegrityError):
            session.execute(
                AnalysisTaskModel.__table__.insert().values(
                    id=uuid4(), analysis_run_id=run_id, project_id=project_id,
                    task_type="parse", status="PENDING", idempotency_key="dup",
                )
            )
            session.commit()
    finally:
        session.close()


def test_idempotency_key_can_repeat_across_runs(session_factory) -> None:
    """不同运行可复用相同幂等键（运行内唯一即可）。"""
    from tender_insight.modules.analysis.infrastructure.models import (
        AnalysisRunModel,
        AnalysisTaskModel,
    )

    session = session_factory()
    try:
        project_id = _seed_project(session)
        run1, run2 = uuid4(), uuid4()
        session.execute(
            AnalysisRunModel.__table__.insert().values(
                id=run1, project_id=project_id, status="QUEUED",
                input_fingerprint="a" * 64,
            )
        )
        session.execute(
            AnalysisRunModel.__table__.insert().values(
                id=run2, project_id=project_id, status="QUEUED",
                input_fingerprint="b" * 64,
            )
        )
        for run_id in (run1, run2):
            session.execute(
                AnalysisTaskModel.__table__.insert().values(
                    id=uuid4(), analysis_run_id=run_id, project_id=project_id,
                    task_type="parse", status="PENDING", idempotency_key="shared",
                )
            )
        session.commit()
    finally:
        session.close()
