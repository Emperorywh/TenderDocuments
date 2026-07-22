"""编辑项目用例测试（B-006 独立验证）。

验证乐观版本冲突不覆盖较新数据。
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from tender_insight.modules.project.application.create_project import (
    CreateProjectCommand,
    CreateProjectUseCase,
)
from tender_insight.modules.project.application.edit_project import (
    EditProjectCommand,
    EditProjectUseCase,
)
from tender_insight.modules.project.domain.exceptions import InvalidProjectDataError
from tender_insight.modules.project.infrastructure.repository import (
    SqlAlchemyProjectRepository,
)
from tender_insight.shared.errors import ConflictError, NotFoundError
from tender_insight.shared.identifiers import Uuid


def _seed_project(session: Session) -> str:
    result = CreateProjectUseCase(SqlAlchemyProjectRepository(session), session).execute(
        CreateProjectCommand(name="p", region="成都", industry="房建", project_type="施工")
    )
    return result.project_id


def _use_case(session: Session) -> EditProjectUseCase:
    return EditProjectUseCase(SqlAlchemyProjectRepository(session), session)


def test_edit_with_correct_version_succeeds(db_session: Session) -> None:
    pid = _seed_project(db_session)
    result = _use_case(db_session).execute(
        EditProjectCommand(project_id=pid, expected_version=1, name="新名称")
    )
    assert result.name == "新名称"
    assert result.version == 2


def test_optimistic_conflict_does_not_overwrite(db_session: Session) -> None:
    """期望版本过期时抛 ConflictError，且不覆盖较新数据。"""
    pid = _seed_project(db_session)
    # 第一次编辑：1 -> 2。
    _use_case(db_session).execute(
        EditProjectCommand(project_id=pid, expected_version=1, name="第一次")
    )
    # 第二次仍用过期 expected_version=1，应冲突。
    with pytest.raises(ConflictError):
        _use_case(db_session).execute(
            EditProjectCommand(project_id=pid, expected_version=1, name="冲突写入")
        )
    # 较新数据（第一次）未被覆盖。
    from tender_insight.shared.identifiers import Uuid

    current = SqlAlchemyProjectRepository(db_session).get(Uuid.from_str(pid))
    assert current is not None
    assert current.name == "第一次"
    assert current.version == 2


def test_edit_unknown_project_not_found(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        _use_case(db_session).execute(
            EditProjectCommand(project_id=str(Uuid.new()), expected_version=1, name="x")
        )


def test_edit_invalid_field_rejected(db_session: Session) -> None:
    pid = _seed_project(db_session)
    with pytest.raises(InvalidProjectDataError):
        _use_case(db_session).execute(
            EditProjectCommand(project_id=pid, expected_version=1, name="   ")
        )
    # 失败不改变数据。
    from tender_insight.shared.identifiers import Uuid

    current = SqlAlchemyProjectRepository(db_session).get(Uuid.from_str(pid))
    assert current is not None
    assert current.name == "p"
    assert current.version == 1
