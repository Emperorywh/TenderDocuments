"""创建上传会话用例测试（C-007 独立验证）。

验证合法元数据返回短期上传信息，并拒绝非法输入与超限。
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from tender_insight.modules.document.application.create_upload_session import (
    CreateUploadSessionCommand,
    CreateUploadSessionUseCase,
)
from tender_insight.modules.document.infrastructure.models import UploadSessionModel
from tender_insight.modules.document.infrastructure.upload_session_repository import (
    SqlAlchemyUploadSessionRepository,
)
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.shared.identifiers import Uuid


def _clock(at: datetime):
    class _Clock:
        def now(self) -> datetime:
            return at

    return _Clock()


def _storage() -> MagicMock:
    storage = MagicMock()
    storage.presigned_put_url.return_value = "https://minio.local/upload"
    return storage


def _seed_project(session: Session) -> Uuid:
    pid = Uuid.new()
    session.add(
        ProjectModel(
            id=pid.value,
            name="p",
            region="成都",
            industry="房建",
            project_type="施工",
            lifecycle_state="ACTIVE",
            version=1,
        )
    )
    session.commit()
    return pid


def _project_exists(session: Session):
    def _check(pid: Uuid) -> bool:
        return session.get(ProjectModel, pid.value) is not None

    return _check


def test_legal_metadata_returns_short_term_upload_info(db_session: Session) -> None:
    pid = _seed_project(db_session)
    now = datetime(2026, 7, 23, 12, tzinfo=UTC)
    use_case = CreateUploadSessionUseCase(
        repository=SqlAlchemyUploadSessionRepository(db_session),
        session=db_session,
        object_storage=_storage(),
        project_exists=_project_exists(db_session),
        max_file_bytes=10 * 1024 * 1024,
        clock=_clock(now),
    )

    info = use_case.execute(
        CreateUploadSessionCommand(
            project_id=str(pid),
            declared_filename="tender.pdf",
            declared_size_bytes=2048,
            declared_mime="application/pdf",
        )
    )

    assert info.session_id
    assert info.object_key.startswith("quarantine/")
    assert info.upload_url == "https://minio.local/upload"
    assert info.method == "PUT"
    # 会话已落库为 PENDING。
    assert db_session.query(UploadSessionModel).count() == 1
    row = db_session.query(UploadSessionModel).one()
    assert row.status == "PENDING"
    assert row.declared_filename == "tender.pdf"


def test_unknown_project_rejected(db_session: Session) -> None:
    use_case = CreateUploadSessionUseCase(
        repository=SqlAlchemyUploadSessionRepository(db_session),
        session=db_session,
        object_storage=_storage(),
        project_exists=_project_exists(db_session),
        max_file_bytes=10 * 1024 * 1024,
        clock=_clock(datetime(2026, 7, 23, tzinfo=UTC)),
    )
    from tender_insight.shared.errors import NotFoundError

    with pytest.raises(NotFoundError):
        use_case.execute(
            CreateUploadSessionCommand(
                project_id=str(Uuid.new()),
                declared_filename="t.pdf",
                declared_size_bytes=10,
                declared_mime="application/pdf",
            )
        )


def test_oversize_rejected(db_session: Session) -> None:
    pid = _seed_project(db_session)
    use_case = CreateUploadSessionUseCase(
        repository=SqlAlchemyUploadSessionRepository(db_session),
        session=db_session,
        object_storage=_storage(),
        project_exists=_project_exists(db_session),
        max_file_bytes=100,
        clock=_clock(datetime(2026, 7, 23, tzinfo=UTC)),
    )
    with pytest.raises(ValueError):
        use_case.execute(
            CreateUploadSessionCommand(
                project_id=str(pid),
                declared_filename="t.pdf",
                declared_size_bytes=10_000,
                declared_mime="application/pdf",
            )
        )
    # 不落库。
    assert db_session.query(UploadSessionModel).count() == 0


def test_object_key_not_guessable(db_session: Session) -> None:
    """暂存键不含原始文件名（不可猜测）。"""
    pid = _seed_project(db_session)
    use_case = CreateUploadSessionUseCase(
        repository=SqlAlchemyUploadSessionRepository(db_session),
        session=db_session,
        object_storage=_storage(),
        project_exists=_project_exists(db_session),
        max_file_bytes=10 * 1024 * 1024,
        clock=_clock(datetime(2026, 7, 23, tzinfo=UTC)),
    )
    info = use_case.execute(
        CreateUploadSessionCommand(
            project_id=str(pid),
            declared_filename="tender.pdf",
            declared_size_bytes=10,
            declared_mime="application/pdf",
        )
    )
    assert "tender.pdf" not in info.object_key
