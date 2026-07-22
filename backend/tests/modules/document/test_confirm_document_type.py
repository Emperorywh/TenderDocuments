"""文件业务类型确认用例测试（C-021 独立验证）。

验证确认后业务类型更新；未确认（OTHER）不进入分析输入集合。
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from tender_insight.modules.document.application.confirm_document_type import (
    ConfirmDocumentTypeCommand,
    ConfirmDocumentTypeUseCase,
)
from tender_insight.modules.document.domain.document import Document
from tender_insight.modules.document.domain.document_types import DocumentBusinessType
from tender_insight.modules.document.infrastructure.document_repositories import (
    SqlAlchemyDocumentRepository,
)
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid


def _seed_document(session: Session, business_type: DocumentBusinessType) -> Uuid:
    from tender_insight.modules.project.infrastructure.models import ProjectModel

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
    doc = Document(
        id=Uuid.new(),
        project_id=project_id,
        business_type=business_type,
        name="tender.pdf",
    )
    repo = SqlAlchemyDocumentRepository(session)
    repo.add(doc)
    session.commit()
    return doc.id


def test_confirm_updates_business_type(db_session: Session) -> None:
    doc_id = _seed_document(db_session, DocumentBusinessType.OTHER)
    result = ConfirmDocumentTypeUseCase(
        repository=SqlAlchemyDocumentRepository(db_session), session=db_session
    ).execute(
        ConfirmDocumentTypeCommand(
            document_id=str(doc_id), business_type=DocumentBusinessType.TENDER_DOC
        )
    )
    assert result.business_type == "TENDER_DOC"
    assert result.confirmed is True


def test_unconfirmed_other_excluded_from_analysis_input(db_session: Session) -> None:
    """未确认（OTHER）的文件 is_business_type_confirmed 为 False。"""
    doc_id = _seed_document(db_session, DocumentBusinessType.OTHER)
    doc = SqlAlchemyDocumentRepository(db_session).get(doc_id)
    assert doc is not None
    assert doc.is_business_type_confirmed is False


def test_reconfirm_changes_type(db_session: Session) -> None:
    """已确认类型可被修正。"""
    doc_id = _seed_document(db_session, DocumentBusinessType.TENDER_DOC)
    ConfirmDocumentTypeUseCase(
        repository=SqlAlchemyDocumentRepository(db_session), session=db_session
    ).execute(
        ConfirmDocumentTypeCommand(
            document_id=str(doc_id), business_type=DocumentBusinessType.ADDENDUM
        )
    )
    doc = SqlAlchemyDocumentRepository(db_session).get(doc_id)
    assert doc is not None
    assert doc.business_type == DocumentBusinessType.ADDENDUM


def test_unknown_document_not_found(db_session: Session) -> None:
    with pytest.raises(NotFoundError):
        ConfirmDocumentTypeUseCase(
            repository=SqlAlchemyDocumentRepository(db_session), session=db_session
        ).execute(
            ConfirmDocumentTypeCommand(
                document_id=str(Uuid.new()),
                business_type=DocumentBusinessType.TENDER_DOC,
            )
        )
