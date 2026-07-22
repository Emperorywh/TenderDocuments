"""恢复待删除项目用例测试（B-013 独立验证）。

验证到期前可恢复，且到期边界规则明确。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from tender_insight.modules.project.application.create_project import (
    CreateProjectCommand,
    CreateProjectUseCase,
)
from tender_insight.modules.project.application.delete_project import (
    DeleteProjectCommand,
    DeleteProjectUseCase,
)
from tender_insight.modules.project.application.recover_project import (
    RecoverProjectCommand,
    RecoverProjectUseCase,
)
from tender_insight.modules.project.domain.project import (
    PENDING_DELETION_RETENTION_DAYS,
    pending_deletion_deadline,
)
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.modules.project.infrastructure.repository import (
    SqlAlchemyProjectRepository,
)
from tender_insight.shared.errors import NotFoundError, PreconditionFailedError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.states import ProjectLifecycleStatus


def _seed_pending_deletion(session: Session, deleted_at: datetime) -> str:
    """创建并删除项目，再将其 pending_deletion_at 覆盖为 deleted_at 以构造边界。"""
    repo = SqlAlchemyProjectRepository(session)
    pid = CreateProjectUseCase(repo, session).execute(
        CreateProjectCommand(name="p", region="成都", industry="房建", project_type="施工")
    ).project_id
    DeleteProjectUseCase(repo, session).execute(DeleteProjectCommand(project_id=pid))
    # 直接更新底层时间戳，控制到期边界（领域不暴露 setter）。
    session.execute(
        update(ProjectModel)
        .where(ProjectModel.id == Uuid.from_str(pid).value)
        .values(pending_deletion_at=deleted_at)
    )
    session.commit()
    return pid


def _clock(at: datetime):
    class _Clock:
        def now(self) -> datetime:
            return at

    return _Clock()


def test_recover_before_deadline_succeeds(db_session: Session) -> None:
    deleted_at = datetime(2026, 7, 23, tzinfo=UTC)
    pid = _seed_pending_deletion(db_session, deleted_at)
    # 29 天后仍在保留期内。
    now = deleted_at + timedelta(days=29)
    RecoverProjectUseCase(SqlAlchemyProjectRepository(db_session), db_session).execute(
        RecoverProjectCommand(project_id=pid), clock=_clock(now)
    )
    project = SqlAlchemyProjectRepository(db_session).get(Uuid.from_str(pid))
    assert project is not None
    assert project.lifecycle_state == ProjectLifecycleStatus.ACTIVE
    assert project.pending_deletion_at is None


def test_recover_at_or_after_deadline_refused(db_session: Session) -> None:
    """到达到期点或之后不可恢复。"""
    deleted_at = datetime(2026, 7, 23, tzinfo=UTC)
    deadline = pending_deletion_deadline(deleted_at)
    assert (deadline - deleted_at).days == PENDING_DELETION_RETENTION_DAYS

    pid = _seed_pending_deletion(db_session, deleted_at)
    with pytest.raises(PreconditionFailedError):
        RecoverProjectUseCase(SqlAlchemyProjectRepository(db_session), db_session).execute(
            RecoverProjectCommand(project_id=pid), clock=_clock(deadline)
        )

    pid2 = _seed_pending_deletion(db_session, deleted_at)
    with pytest.raises(PreconditionFailedError):
        RecoverProjectUseCase(SqlAlchemyProjectRepository(db_session), db_session).execute(
            RecoverProjectCommand(project_id=pid2), clock=_clock(deadline + timedelta(seconds=1))
        )


def test_recover_unknown_raises_not_found(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        RecoverProjectUseCase(SqlAlchemyProjectRepository(db_session), db_session).execute(
            RecoverProjectCommand(project_id=str(Uuid.new())),
            clock=_clock(datetime(2026, 7, 23, tzinfo=UTC)),
        )


def test_deadline_boundary_is_exclusive() -> None:
    """到期点 = 删除时间 + 30 天；到达到期点即过期（>= 判定）。"""
    deleted_at = datetime(2026, 7, 23, tzinfo=UTC)
    deadline = pending_deletion_deadline(deleted_at)
    assert deadline == datetime(2026, 8, 22, tzinfo=UTC)
