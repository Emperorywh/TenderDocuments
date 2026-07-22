"""恢复归档项目用例测试（B-011 独立验证）。

验证恢复后字段与关联数据保持不变。
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
from tender_insight.modules.project.application.restore_project import (
    RestoreProjectCommand,
    RestoreProjectUseCase,
)
from tender_insight.modules.project.infrastructure.repository import (
    SqlAlchemyProjectRepository,
)
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.pagination import PageRequest
from tender_insight.shared.states import ProjectLifecycleStatus


def _create(session: Session, name: str) -> str:
    return CreateProjectUseCase(SqlAlchemyProjectRepository(session), session).execute(
        CreateProjectCommand(name=name, region="成都", industry="房建", project_type="施工")
    ).project_id


def test_restore_returns_to_active_with_fields_preserved(db_session: Session) -> None:
    """恢复后状态 ACTIVE、字段不变、重新出现在活动列表。"""
    pid = _create(db_session, "原始名称")
    repo = SqlAlchemyProjectRepository(db_session)
    ArchiveProjectUseCase(repo, db_session).execute(ArchiveProjectCommand(project_id=pid))

    RestoreProjectUseCase(repo, db_session).execute(RestoreProjectCommand(project_id=pid))

    project = repo.get(Uuid.from_str(pid))
    assert project is not None
    assert project.lifecycle_state == ProjectLifecycleStatus.ACTIVE
    # 字段保持不变。
    assert project.name == "原始名称"
    assert project.region == "成都"

    result = list_projects(db_session, PageRequest(page=1, page_size=10))
    assert pid in {i.project_id for i in result.items}


def test_restore_unknown_raises_not_found(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        RestoreProjectUseCase(SqlAlchemyProjectRepository(db_session), db_session).execute(
            RestoreProjectCommand(project_id=str(Uuid.new()))
        )
