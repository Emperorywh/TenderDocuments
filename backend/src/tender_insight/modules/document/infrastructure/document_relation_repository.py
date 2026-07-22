"""DocumentRelation SQLAlchemy 仓储适配器（C-024 支撑）。"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from tender_insight.modules.document.infrastructure.models import DocumentRelationModel
from tender_insight.shared.identifiers import Uuid


class SqlAlchemyDocumentRelationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        project_id: Uuid,
        source_document_id: Uuid,
        target_document_id: Uuid,
        relation_type: str,
    ) -> None:
        self._session.add(
            DocumentRelationModel(
                id=uuid4(),
                project_id=project_id.value,
                source_document_id=source_document_id.value,
                target_document_id=target_document_id.value,
                relation_type=relation_type,
            )
        )

    def relations_in_project(
        self, project_id: Uuid, *, relation_type: str
    ) -> list[tuple[Uuid, Uuid]]:
        stmt = select(DocumentRelationModel).where(
            DocumentRelationModel.project_id == project_id.value,
            DocumentRelationModel.relation_type == relation_type,
        )
        rows = self._session.execute(stmt).scalars().all()
        return [(Uuid(r.source_document_id), Uuid(r.target_document_id)) for r in rows]
