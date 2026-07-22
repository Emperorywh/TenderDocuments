"""文件只读列表投影（C-029）。

分页查询项目下的逻辑文件（含版本数与确认状态），只读，不写领域表。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tender_insight.modules.document.infrastructure.models import (
    DocumentModel,
    DocumentVersionModel,
)
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.pagination import Page, PageRequest


class DocumentListItem(BaseModel):
    """文件列表项。"""

    document_id: str
    project_id: str
    business_type: str
    name: str
    confirmed: bool
    version_count: int
    created_at: datetime


def list_documents(
    session: Session, project_id: Uuid, page_request: PageRequest
) -> Page[DocumentListItem]:
    """分页查询项目下的逻辑文件。"""
    base_filter = DocumentModel.project_id == project_id.value

    total = session.scalar(
        select(func.count()).select_from(DocumentModel).where(base_filter)
    ) or 0

    # 版本数子查询。
    version_counts = (
        select(
            DocumentVersionModel.document_id,
            func.count(DocumentVersionModel.id).label("vc"),
        )
        .group_by(DocumentVersionModel.document_id)
        .subquery()
    )
    stmt = (
        select(DocumentModel, version_counts.c.vc)
        .outerjoin(version_counts, version_counts.c.document_id == DocumentModel.id)
        .where(base_filter)
        .order_by(DocumentModel.created_at.desc())
        .offset(page_request.offset)
        .limit(page_request.page_size)
    )
    items: list[DocumentListItem] = []
    for doc, vc in session.execute(stmt).all():
        items.append(
            DocumentListItem(
                document_id=str(doc.id),
                project_id=str(doc.project_id),
                business_type=doc.business_type,
                name=doc.name,
                confirmed=doc.business_type != "OTHER",
                version_count=int(vc or 0),
                created_at=doc.created_at,
            )
        )
    return Page(items=items, total=total, page=page_request.page, page_size=page_request.page_size)
