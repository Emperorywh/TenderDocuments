"""项目命令操作记录集成测试（B-017 独立验证）。

验证每个项目命令恰好产生一条操作记录（成功同事务、失败独立事务持久化）。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from tender_insight.modules.operation_log.infrastructure.models import OperationLogModel
from tender_insight.modules.operation_log.infrastructure.recorder import (
    SqlAlchemyOperationRecorder,
)
from tender_insight.modules.project.application.archive_project import (
    ArchiveProjectCommand,
    ArchiveProjectUseCase,
)
from tender_insight.modules.project.application.create_project import (
    CreateProjectCommand,
    CreateProjectUseCase,
)
from tender_insight.modules.project.application.delete_project import (
    DeleteProjectCommand,
    DeleteProjectUseCase,
)
from tender_insight.modules.project.application.edit_project import (
    EditProjectCommand,
    EditProjectUseCase,
)
from tender_insight.modules.project.application.recover_project import (
    RecoverProjectCommand,
    RecoverProjectUseCase,
)
from tender_insight.modules.project.application.restore_project import (
    RestoreProjectCommand,
    RestoreProjectUseCase,
)
from tender_insight.modules.project.domain.exceptions import InvalidProjectDataError
from tender_insight.modules.project.infrastructure.repository import (
    SqlAlchemyProjectRepository,
)
from tender_insight.shared.errors import NotFoundError


def _open_recorder(session: Session) -> SqlAlchemyOperationRecorder:
    return SqlAlchemyOperationRecorder(session)


def _use_case_kwargs(session: Session, session_factory: sessionmaker[Session]) -> dict:
    return {
        "session_factory": session_factory,
        "open_recorder": _open_recorder,
    }


def _create(session: Session, session_factory, name: str = "p") -> str:
    return CreateProjectUseCase(
        SqlAlchemyProjectRepository(session), session, **_use_case_kwargs(session, session_factory)
    ).execute(
        CreateProjectCommand(name=name, region="成都", industry="房建", project_type="施工")
    ).project_id


def test_create_produces_one_success_record(db_session: Session, session_factory) -> None:
    _create(db_session, session_factory)
    rows = db_session.query(OperationLogModel).all()
    assert len(rows) == 1
    assert rows[0].action == "project.create"
    assert rows[0].result == "success"
    assert rows[0].error_code is None


def test_failed_create_produces_one_failure_record_persisted(
    db_session: Session, session_factory
) -> None:
    """失败命令记录一条 failure 且不受业务回滚影响。"""
    repo = SqlAlchemyProjectRepository(db_session)
    with pytest.raises(InvalidProjectDataError):
        CreateProjectUseCase(repo, db_session, **_use_case_kwargs(db_session, session_factory)).execute(
            CreateProjectCommand(name="   ", region="成都", industry="房建", project_type="施工")
        )
    # 失败记录在独立事务中持久化。
    rows = db_session.query(OperationLogModel).all()
    assert len(rows) == 1
    assert rows[0].result == "failure"
    assert rows[0].error_code == "INVALID_PROJECT_DATA"


def test_each_command_produces_exactly_one_record(db_session: Session, session_factory) -> None:
    """edit/archive/restore/delete/recover 各产生恰好一条成功记录。"""
    repo = SqlAlchemyProjectRepository(db_session)
    kw = _use_case_kwargs(db_session, session_factory)

    pid = _create(db_session, session_factory)

    EditProjectUseCase(repo, db_session, **kw).execute(
        EditProjectCommand(project_id=pid, expected_version=1, name="改名")
    )
    ArchiveProjectUseCase(repo, db_session, **kw).execute(ArchiveProjectCommand(project_id=pid))
    RestoreProjectUseCase(repo, db_session, **kw).execute(RestoreProjectCommand(project_id=pid))
    DeleteProjectUseCase(repo, db_session, **kw).execute(DeleteProjectCommand(project_id=pid))

    # recover：待删除期内的项目可恢复（用未来时间避开边界）。
    RecoverProjectUseCase(repo, db_session, **kw).execute(
        RecoverProjectCommand(project_id=pid), clock=_fixed_clock(datetime(2026, 7, 23, tzinfo=UTC))
    )

    rows = db_session.query(OperationLogModel).all()
    # create + edit + archive + restore + delete + recover = 6 条，全部成功。
    assert len(rows) == 6
    assert {r.action for r in rows} == {
        "project.create",
        "project.edit",
        "project.archive",
        "project.restore",
        "project.delete",
        "project.recover",
    }
    assert all(r.result == "success" for r in rows)


def test_not_found_command_produces_one_failure_record(db_session: Session, session_factory) -> None:
    repo = SqlAlchemyProjectRepository(db_session)
    kw = _use_case_kwargs(db_session, session_factory)
    with pytest.raises(NotFoundError):
        ArchiveProjectUseCase(repo, db_session, **kw).execute(
            ArchiveProjectCommand(project_id="00000000-0000-0000-0000-000000000001")
        )
    rows = db_session.query(OperationLogModel).all()
    assert len(rows) == 1
    assert rows[0].result == "failure"
    assert rows[0].error_code == "NOT_FOUND"


def _fixed_clock(at: datetime):
    class _Clock:
        def now(self) -> datetime:
            return at - timedelta(days=1)  # 在保留期内

    return _Clock()
