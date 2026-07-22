"""归档项目用例测试（B-010 独立验证）。

验证归档后默认列表不可见且数据未删除。
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from tender_insight.modules.project.application.archive_project import (
    ArchiveProjectCommand,
    ArchiveProjectUseCase,
)
from tender_insight.modules.project.application.create_project import (
    CreateProjectCommand,
    CreateProjectUseCase,
)
from tender_insight.modules.project.application.list_projects import list_projects
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.modules.project.infrastructure.repository import (
    SqlAlchemyProjectRepository,
)
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.pagination import PageRequest
from tender_insight.shared.states import ProjectLifecycleStatus


def _seed(session: Session) -> str:
    return CreateProjectUseCase(SqlAlchemyProjectRepository(session), session).execute(
        CreateProjectCommand(name="p", region="成都", industry="房建", project_type="施工")
    ).project_id


def test_archive_hides_from_default_list_but_keeps_data(db_session: Session) -> None:
    """归档后默认列表不可见，但数据仍存在。"""
    pid = _seed(db_session)
    ArchiveProjectUseCase(SqlAlchemyProjectRepository(db_session), db_session).execute(
        ArchiveProjectCommand(project_id=pid)
    )

    # 默认列表（活动）不含该项目。
    result = list_projects(db_session, PageRequest(page=1, page_size=10))
    assert pid not in {i.project_id for i in result.items}

    # 数据未删除：直接查询仍存在，状态为 ARCHIVED。
    project = SqlAlchemyProjectRepository(db_session).get(Uuid.from_str(pid))
    assert project is not None
    assert project.lifecycle_state == ProjectLifecycleStatus.ARCHIVED
    assert db_session.query(ProjectModel).count() == 1


def test_archive_unknown_raises_not_found(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        ArchiveProjectUseCase(SqlAlchemyProjectRepository(db_session), db_session).execute(
            ArchiveProjectCommand(project_id=str(Uuid.new()))
        )


def test_archived_listed_when_filtering_archived(db_session: Session) -> None:
    """显式按 ARCHIVED 过滤可列出归档项目。"""
    pid = _seed(db_session)
    ArchiveProjectUseCase(SqlAlchemyProjectRepository(db_session), db_session).execute(
        ArchiveProjectCommand(project_id=pid)
    )
    result = list_projects(
        db_session,
        PageRequest(page=1, page_size=10),
        states=frozenset({ProjectLifecycleStatus.ARCHIVED}),
    )
    assert result.total == 1
    assert result.items[0].project_id == pid
