"""Project 仓储测试（B-003 独立验证）。

验证创建后可按 project_id 回读，且事务回滚不留数据。使用临时 SQLite + 迁移。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from tender_insight.modules.project.domain.project import Project
from tender_insight.modules.project.infrastructure.repository import (
    SqlAlchemyProjectRepository,
)


def _make_project() -> Project:
    return Project.create(
        name="天府新区房建项目",
        region="成都",
        industry="房屋建筑工程",
        project_type="施工",
    )


def test_add_and_get_roundtrip(db_session: Session) -> None:
    """创建后按 project_id 可回读，字段一致。"""
    repo = SqlAlchemyProjectRepository(db_session)
    project = _make_project()
    repo.add(project)
    db_session.commit()

    fetched = repo.get(project.id)
    assert fetched is not None
    assert fetched.id == project.id
    assert fetched.name == "天府新区房建项目"
    assert fetched.region == "成都"
    assert fetched.industry == "房屋建筑工程"
    assert fetched.project_type == "施工"
    assert fetched.version == 1


def test_rollback_leaves_no_data(db_session: Session, session_factory) -> None:
    """事务回滚后不留数据。"""
    repo = SqlAlchemyProjectRepository(db_session)
    project = _make_project()
    repo.add(project)
    db_session.rollback()  # 不提交即回滚

    # 回读应得 None。
    assert repo.get(project.id) is None

    # 新会话也查不到，确认未落库。
    other = session_factory()
    try:
        assert SqlAlchemyProjectRepository(other).get(project.id) is None
    finally:
        other.close()


def test_get_unknown_returns_none(db_session: Session) -> None:
    repo = SqlAlchemyProjectRepository(db_session)
    from tender_insight.shared.identifiers import Uuid

    assert repo.get(Uuid.new()) is None


def test_save_persists_changes(db_session: Session) -> None:
    """save 保存领域变更（归档）并回读一致。"""
    repo = SqlAlchemyProjectRepository(db_session)
    project = _make_project()
    repo.add(project)
    db_session.commit()

    project.archive()
    repo.save(project)
    db_session.commit()

    fetched = repo.get(project.id)
    assert fetched is not None
    from tender_insight.shared.states import ProjectLifecycleStatus

    assert fetched.lifecycle_state == ProjectLifecycleStatus.ARCHIVED
    assert fetched.version == 2
    assert fetched.archived_at is not None
