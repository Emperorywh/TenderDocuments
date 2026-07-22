"""文件替代关系命令测试（C-024 独立验证）。

验证循环替代被拒绝、跨项目被拒、自引用被拒；历史版本不被覆盖。
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from tender_insight.modules.document.application.create_document_relation import (
    CreateDocumentRelationCommand,
    CreateDocumentRelationUseCase,
)
from tender_insight.modules.document.domain.document import Document
from tender_insight.modules.document.domain.document_types import (
    DocumentBusinessType,
    DocumentRelationType,
)
from tender_insight.modules.document.infrastructure.document_relation_repository import (
    SqlAlchemyDocumentRelationRepository,
)
from tender_insight.modules.document.infrastructure.document_repositories import (
    SqlAlchemyDocumentRepository,
)
from tender_insight.modules.document.infrastructure.models import DocumentVersionModel
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.shared.errors import ConflictError
from tender_insight.shared.identifiers import Uuid


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


def _seed_document(session: Session, project_id: Uuid) -> Uuid:
    doc = Document(
        id=Uuid.new(),
        project_id=project_id,
        business_type=DocumentBusinessType.TENDER_DOC,
        name="t.pdf",
    )
    repo = SqlAlchemyDocumentRepository(session)
    repo.add(doc)
    session.commit()
    return doc.id


def _use_case(session: Session) -> CreateDocumentRelationUseCase:
    return CreateDocumentRelationUseCase(
        document_repository=SqlAlchemyDocumentRepository(session),
        relation_repository=SqlAlchemyDocumentRelationRepository(session),
        session=session,
    )


def test_replaces_relation_created(db_session: Session) -> None:
    pid = _seed_project(db_session)
    a = _seed_document(db_session, pid)
    b = _seed_document(db_session, pid)
    result = _use_case(db_session).execute(
        CreateDocumentRelationCommand(
            project_id=str(pid),
            source_document_id=str(a),
            target_document_id=str(b),
            relation_type=DocumentRelationType.REPLACES,
        )
    )
    assert result.relation_type == "REPLACES"


def test_cycle_rejected(db_session: Session) -> None:
    """A 替代 B 后，B 替代 A 被拒（循环）。"""
    pid = _seed_project(db_session)
    a = _seed_document(db_session, pid)
    b = _seed_document(db_session, pid)
    uc = _use_case(db_session)
    uc.execute(
        CreateDocumentRelationCommand(
            project_id=str(pid),
            source_document_id=str(a),
            target_document_id=str(b),
            relation_type=DocumentRelationType.REPLACES,
        )
    )
    with pytest.raises(ConflictError):
        uc.execute(
            CreateDocumentRelationCommand(
                project_id=str(pid),
                source_document_id=str(b),
                target_document_id=str(a),
                relation_type=DocumentRelationType.REPLACES,
            )
        )


def test_cross_project_rejected(db_session: Session) -> None:
    pid1 = _seed_project(db_session)
    pid2 = _seed_project(db_session)
    a = _seed_document(db_session, pid1)
    b = _seed_document(db_session, pid2)
    with pytest.raises(ConflictError):
        _use_case(db_session).execute(
            CreateDocumentRelationCommand(
                project_id=str(pid1),
                source_document_id=str(a),
                target_document_id=str(b),
                relation_type=DocumentRelationType.SUPPLEMENTS,
            )
        )


def test_self_reference_rejected(db_session: Session) -> None:
    pid = _seed_project(db_session)
    a = _seed_document(db_session, pid)
    with pytest.raises(ConflictError):
        _use_case(db_session).execute(
            CreateDocumentRelationCommand(
                project_id=str(pid),
                source_document_id=str(a),
                target_document_id=str(a),
                relation_type=DocumentRelationType.REPLACES,
            )
        )


def test_relation_does_not_overwrite_versions(db_session: Session) -> None:
    """关系独立追加，不修改既有版本。"""
    pid = _seed_project(db_session)
    a = _seed_document(db_session, pid)
    b = _seed_document(db_session, pid)
    before = db_session.query(DocumentVersionModel).count()
    _use_case(db_session).execute(
        CreateDocumentRelationCommand(
            project_id=str(pid),
            source_document_id=str(a),
            target_document_id=str(b),
            relation_type=DocumentRelationType.REFERENCES,
        )
    )
    after = db_session.query(DocumentVersionModel).count()
    assert before == after  # 版本表无变化
