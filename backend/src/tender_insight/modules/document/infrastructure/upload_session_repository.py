"""UploadSession SQLAlchemy 仓储适配器（C-007 支撑）。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from tender_insight.modules.document.domain.upload_session import UploadSession
from tender_insight.modules.document.infrastructure.models import UploadSessionModel
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.states import UploadSessionStatus


def _ensure_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class SqlAlchemyUploadSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, upload_session: UploadSession) -> None:
        self._session.add(_to_orm(upload_session))

    def get(self, session_id: Uuid) -> UploadSession | None:
        orm = self._session.get(UploadSessionModel, session_id.value)
        return _to_domain(orm) if orm is not None else None

    def save(self, upload_session: UploadSession) -> None:
        orm = self._session.get(UploadSessionModel, upload_session.id.value)
        if orm is None:
            self._session.add(_to_orm(upload_session))
            return
        orm.status = upload_session.status.value
        orm.completed_at = upload_session.completed_at


def _to_orm(upload_session: UploadSession) -> UploadSessionModel:
    return UploadSessionModel(
        id=upload_session.id.value,
        project_id=upload_session.project_id.value,
        declared_filename=upload_session.declared_filename,
        declared_size_bytes=upload_session.declared_size_bytes,
        declared_mime=upload_session.declared_mime,
        object_key=upload_session.object_key,
        status=upload_session.status.value,
        created_at=upload_session.created_at,
        expires_at=upload_session.expires_at,
        completed_at=upload_session.completed_at,
    )


def _to_domain(orm: UploadSessionModel) -> UploadSession:
    return UploadSession(
        id=Uuid(orm.id),
        project_id=Uuid(orm.project_id),
        declared_filename=orm.declared_filename,
        declared_size_bytes=orm.declared_size_bytes,
        declared_mime=orm.declared_mime,
        object_key=orm.object_key,
        status=UploadSessionStatus(orm.status),
        created_at=_ensure_aware(orm.created_at),  # type: ignore[arg-type]
        expires_at=_ensure_aware(orm.expires_at),  # type: ignore[arg-type]
        completed_at=_ensure_aware(orm.completed_at),
    )
