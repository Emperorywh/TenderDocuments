"""文件发布日期确认用例测试（C-022 独立验证）。

验证带时区日期可设置，无时区或非法日期被拒绝。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from tender_insight.modules.document.application.confirm_published_date import (
    ConfirmPublishedDateCommand,
    ConfirmPublishedDateUseCase,
)
from tender_insight.modules.document.domain.document_version import DocumentVersion
from tender_insight.modules.document.infrastructure.document_repositories import (
    SqlAlchemyDocumentVersionRepository,
)
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.shared.business_time import NaiveBusinessTimeError
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid


def _seed_version(session: Session) -> Uuid:
    from tender_insight.modules.document.domain.document import Document
    from tender_insight.modules.document.domain.document_types import DocumentBusinessType
    from tender_insight.modules.document.infrastructure.document_repositories import (
        SqlAlchemyDocumentRepository,
    )

    project_id = Uuid.new()
    session.add(
        ProjectModel(
            id=project_id.value,
            name="p",
            region="成都",
            industry="房建",
            project_type="施工",
            lifecycle_state="ACTIVE",
            version=1,
        )
    )
    session.commit()
    doc_repo = SqlAlchemyDocumentRepository(session)
    document = Document(
        id=Uuid.new(),
        project_id=project_id,
        business_type=DocumentBusinessType.TENDER_DOC,
        name="t.pdf",
    )
    doc_repo.add(document)
    session.commit()
    version = DocumentVersion.create(
        version_id=Uuid.new(),
        document_id=document.id,
        version_number=1,
        original_object_key="original/abc",
        sha256="a" * 64,
        size_bytes=10,
        mime="application/pdf",
    )
    repo = SqlAlchemyDocumentVersionRepository(session)
    repo.add(version)
    session.commit()
    return version.id


def test_aware_datetime_succeeds(db_session: Session) -> None:
    vid = _seed_version(db_session)
    result = ConfirmPublishedDateUseCase(
        repository=SqlAlchemyDocumentVersionRepository(db_session), session=db_session
    ).execute(
        ConfirmPublishedDateCommand(
            version_id=str(vid),
            published_at=datetime(2026, 7, 23, tzinfo=UTC),
        )
    )
    assert result.published_at == datetime(2026, 7, 23, tzinfo=UTC)


def test_naive_datetime_rejected(db_session: Session) -> None:
    """无时区日期被领域层拒绝。"""
    vid = _seed_version(db_session)
    use_case = ConfirmPublishedDateUseCase(
        repository=SqlAlchemyDocumentVersionRepository(db_session), session=db_session
    )
    # Pydantic 解析无时区 ISO 字符串为 naive datetime；领域层拒绝。
    cmd = ConfirmPublishedDateCommand.model_validate(
        {"version_id": str(vid), "published_at": "2026-07-23T00:00:00"}
    )
    with pytest.raises(NaiveBusinessTimeError):
        use_case.execute(cmd)


def test_unknown_version_not_found(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        ConfirmPublishedDateUseCase(
            repository=SqlAlchemyDocumentVersionRepository(db_session), session=db_session
        ).execute(
            ConfirmPublishedDateCommand(
                version_id=str(Uuid.new()),
                published_at=datetime(2026, 7, 23, tzinfo=UTC),
            )
        )
