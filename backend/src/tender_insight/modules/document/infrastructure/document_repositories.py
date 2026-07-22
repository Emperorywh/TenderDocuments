"""Document 与 DocumentVersion SQLAlchemy 仓储适配器（C-017 支撑）。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tender_insight.modules.document.domain.document import Document
from tender_insight.modules.document.domain.document_types import DocumentBusinessType
from tender_insight.modules.document.domain.document_version import DocumentVersion
from tender_insight.modules.document.infrastructure.models import (
    DocumentModel,
    DocumentVersionModel,
)
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.states import DocumentVersionStatus


class SqlAlchemyDocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, document: Document) -> None:
        self._session.add(
            DocumentModel(
                id=document.id.value,
                project_id=document.project_id.value,
                business_type=document.business_type.value,
                name=document.name,
            )
        )

    def get(self, document_id: Uuid) -> Document | None:
        orm = self._session.get(DocumentModel, document_id.value)
        if orm is None:
            return None
        return Document(
            id=Uuid(orm.id),
            project_id=Uuid(orm.project_id),
            business_type=DocumentBusinessType(orm.business_type),
            name=orm.name,
        )

    def save(self, document: Document) -> None:
        orm = self._session.get(DocumentModel, document.id.value)
        if orm is None:
            self._session.add(
                DocumentModel(
                    id=document.id.value,
                    project_id=document.project_id.value,
                    business_type=document.business_type.value,
                    name=document.name,
                )
            )
            return
        orm.business_type = document.business_type.value
        orm.name = document.name


class SqlAlchemyDocumentVersionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, version: DocumentVersion) -> None:
        self._session.add(
            DocumentVersionModel(
                id=version.id.value,
                document_id=version.document_id.value,
                version_number=version.version_number,
                original_object_key=version.original_object_key,
                sha256=version.sha256,
                size_bytes=version.size_bytes,
                mime=version.mime,
                status=version.status.value,
                canonical_object_key=version.canonical_object_key,
                page_count=version.page_count,
                published_date=version.published_date,
                effect_order=version.effect_order,
            )
        )

    def next_version_number(self, document_id: Uuid) -> int:
        current = self._session.scalar(
            select(func.max(DocumentVersionModel.version_number)).where(
                DocumentVersionModel.document_id == document_id.value
            )
        )
        return (current or 0) + 1

    def exists_by_sha256_in_project(self, project_id: Uuid, sha256: str) -> bool:
        """项目内是否已存在同哈希版本（联接 documents 取 project_id）。"""
        stmt = (
            select(func.count())
            .select_from(DocumentVersionModel)
            .join(DocumentModel, DocumentModel.id == DocumentVersionModel.document_id)
            .where(
                DocumentModel.project_id == project_id.value,
                DocumentVersionModel.sha256 == sha256,
            )
        )
        return (self._session.scalar(stmt) or 0) > 0


def version_from_orm(orm: DocumentVersionModel) -> DocumentVersion:
    """ORM → 领域 DocumentVersion（含只读核心字段）。"""
    version = DocumentVersion(
        _id=Uuid(orm.id),
        _document_id=Uuid(orm.document_id),
        _version_number=orm.version_number,
        _original_object_key=orm.original_object_key,
        _sha256=orm.sha256,
        _size_bytes=orm.size_bytes,
        _mime=orm.mime,
        status=DocumentVersionStatus(orm.status),
        canonical_object_key=orm.canonical_object_key,
        page_count=orm.page_count,
        published_date=orm.published_date,
        effect_order=orm.effect_order,
    )
    return version
