"""请求删除项目用例测试（B-012 独立验证）。

验证删除只改变生命周期，不立即物理清除。
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from tender_insight.modules.project.application.create_project import (
    CreateProjectCommand,
    CreateProjectUseCase,
)
from tender_insight.modules.project.application.delete_project import (
    DeleteProjectCommand,
    DeleteProjectUseCase,
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


def _create(session: Session) -> str:
    return CreateProjectUseCase(SqlAlchemyProjectRepository(session), session).execute(
        CreateProjectCommand(name="p", region="成都", industry="房建", project_type="施工")
    ).project_id


def test_delete_marks_pending_without_physical_removal(db_session: Session) -> None:
    """删除进入待删除期，数据仍存在，未物理清除。"""
    pid = _create(db_session)
    DeleteProjectUseCase(SqlAlchemyProjectRepository(db_session), db_session).execute(
        DeleteProjectCommand(project_id=pid)
    )

    project = SqlAlchemyProjectRepository(db_session).get(Uuid.from_str(pid))
    assert project is not None
    assert project.lifecycle_state == ProjectLifecycleStatus.PENDING_DELETION
    assert project.pending_deletion_at is not None
    # 数据未物理清除。
    assert db_session.query(ProjectModel).count() == 1
    # 不在活动列表。
    result = list_projects(db_session, PageRequest(page=1, page_size=10))
    assert pid not in {i.project_id for i in result.items}


def test_delete_unknown_raises_not_found(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        DeleteProjectUseCase(SqlAlchemyProjectRepository(db_session), db_session).execute(
            DeleteProjectCommand(project_id=str(Uuid.new()))
        )


def test_archived_project_can_be_deleted(db_session: Session) -> None:
    """归档项目也可进入待删除期（ARCHIVED -> PENDING_DELETION）。"""
    from tender_insight.modules.project.application.archive_project import (
        ArchiveProjectCommand,
        ArchiveProjectUseCase,
    )

    pid = _create(db_session)
    repo = SqlAlchemyProjectRepository(db_session)
    ArchiveProjectUseCase(repo, db_session).execute(ArchiveProjectCommand(project_id=pid))
    DeleteProjectUseCase(repo, db_session).execute(DeleteProjectCommand(project_id=pid))
    project = repo.get(Uuid.from_str(pid))
    assert project is not None
    assert project.lifecycle_state == ProjectLifecycleStatus.PENDING_DELETION
