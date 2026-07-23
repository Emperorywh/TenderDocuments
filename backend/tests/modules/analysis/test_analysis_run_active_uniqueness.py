"""活动运行唯一约束测试（D-003 独立验证）。

验证同项目同输入指纹只能存在一个活动（非终态）运行；终态运行不占用名额。
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from tender_insight.modules.analysis.domain.analysis_run import (
    ACTIVE_RUN_STATUSES,
    TERMINAL_RUN_STATUSES,
    is_active_run_status,
)


def _insert_run(session, *, project_id, fingerprint, status) -> None:
    from tender_insight.modules.analysis.infrastructure.models import AnalysisRunModel

    session.execute(
        AnalysisRunModel.__table__.insert().values(
            id=uuid4(),
            project_id=project_id,
            status=status,
            input_fingerprint=fingerprint,
        )
    )
    session.commit()


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


def test_active_and_terminal_sets_partition_all_statuses() -> None:
    """活动集与终态集覆盖全部运行状态且不重叠（单一权威定义）。"""
    from tender_insight.shared.states import AnalysisRunStatus

    all_statuses = set(AnalysisRunStatus)
    assert all_statuses == (ACTIVE_RUN_STATUSES | TERMINAL_RUN_STATUSES)
    assert not (ACTIVE_RUN_STATUSES & TERMINAL_RUN_STATUSES)
    assert is_active_run_status(AnalysisRunStatus.DRAFT)
    assert not is_active_run_status(AnalysisRunStatus.PUBLISHED)


def test_second_active_run_same_project_input_rejected(session_factory) -> None:
    """同项目同输入指纹的第二个活动运行被数据库拒绝。"""
    session = session_factory()
    try:
        pid = _seed_project(session)
        _insert_run(session, project_id=pid, fingerprint="a" * 64, status="DRAFT")
        with pytest.raises(IntegrityError):
            _insert_run(
                session, project_id=pid, fingerprint="a" * 64, status="QUEUED"
            )
    finally:
        session.close()


def test_terminal_run_does_not_block_new_active_run(session_factory) -> None:
    """终态运行不占名额：CANCELLED 后可再建同输入活动运行。"""
    session = session_factory()
    try:
        pid = _seed_project(session)
        # 终态（CANCELLED）不占用唯一名额。
        _insert_run(session, project_id=pid, fingerprint="b" * 64, status="CANCELLED")
        # 现在可再建一个活动运行（同输入）。
        _insert_run(session, project_id=pid, fingerprint="b" * 64, status="DRAFT")
    finally:
        session.close()


def test_multiple_terminal_runs_same_input_allowed(session_factory) -> None:
    """多个终态运行（同输入）可并存：均不占用活动名额。"""
    session = session_factory()
    try:
        pid = _seed_project(session)
        _insert_run(session, project_id=pid, fingerprint="b2" * 32, status="CANCELLED")
        _insert_run(session, project_id=pid, fingerprint="b2" * 32, status="FAILED")
        _insert_run(session, project_id=pid, fingerprint="b2" * 32, status="OUTDATED")
    finally:
        session.close()


def test_published_does_not_block_new_active_run(session_factory) -> None:
    """PUBLISHED 非活动，允许同输入重分析（新活动运行可创建）。"""
    session = session_factory()
    try:
        pid = _seed_project(session)
        _insert_run(session, project_id=pid, fingerprint="c" * 64, status="PUBLISHED")
        _insert_run(session, project_id=pid, fingerprint="c" * 64, status="DRAFT")
    finally:
        session.close()


def test_different_project_or_input_allowed(session_factory) -> None:
    """不同项目或不同输入指纹的活动运行可并存。"""
    session = session_factory()
    try:
        p1 = _seed_project(session)
        p2 = _seed_project(session)
        _insert_run(session, project_id=p1, fingerprint="d" * 64, status="DRAFT")
        # 不同项目，同指纹。
        _insert_run(session, project_id=p2, fingerprint="d" * 64, status="DRAFT")
        # 同项目，不同指纹。
        _insert_run(session, project_id=p1, fingerprint="e" * 64, status="QUEUED")
    finally:
        session.close()
