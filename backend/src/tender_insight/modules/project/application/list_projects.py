"""项目列表只读投影（B-008）。

按分页与排序查询项目，用于列表展示。投影只读：仅执行 SELECT，不写领域表
（SPEC.md 第 3.2 节“查询展示可使用只读投影，但不得通过投影写回领域表”）。

默认只列活动项目（归档/待删除/已清除不出现在活动列表，SPEC.md 第 6.3 节）。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.shared.pagination import Page, PageRequest, SortDirection
from tender_insight.shared.states import ProjectLifecycleStatus

# 允许排序的字段白名单，防止任意列名注入。
_SORTABLE_COLUMNS = {
    "name": ProjectModel.name,
    "region": ProjectModel.region,
    "industry": ProjectModel.industry,
    "updated_at": ProjectModel.updated_at,
    "created_at": ProjectModel.created_at,
}


class ProjectListItem(BaseModel):
    """项目列表项投影。"""

    project_id: str
    name: str
    region: str
    industry: str
    project_type: str
    lifecycle_state: str
    updated_at: datetime
    version: int


def list_projects(
    session: Session,
    page_request: PageRequest,
    *,
    states: frozenset[ProjectLifecycleStatus] | None = None,
) -> Page[ProjectListItem]:
    """分页查询项目；默认仅活动项目。

    states 为 None 时默认只查 ACTIVE；显式传入可列出归档等待定状态集合。
    """
    active_states = states if states is not None else frozenset({ProjectLifecycleStatus.ACTIVE})

    # 总数（按状态过滤）。
    total = session.scalar(
        select(func.count())
        .select_from(ProjectModel)
        .where(ProjectModel.lifecycle_state.in_([s.value for s in active_states]))
    )
    total = total or 0

    # 主查询：过滤 + 排序 + 分页。
    stmt = select(ProjectModel).where(
        ProjectModel.lifecycle_state.in_([s.value for s in active_states])
    )
    stmt = _apply_sort(stmt, page_request)
    stmt = stmt.offset(page_request.offset).limit(page_request.page_size)

    rows = session.execute(stmt).scalars().all()
    items = [
        ProjectListItem(
            project_id=str(row.id),
            name=row.name,
            region=row.region,
            industry=row.industry,
            project_type=row.project_type,
            lifecycle_state=row.lifecycle_state,
            updated_at=row.updated_at,
            version=row.version,
        )
        for row in rows
    ]
    return Page(items=items, total=total, page=page_request.page, page_size=page_request.page_size)


def _apply_sort(stmt, page_request: PageRequest):
    """把排序规格映射为 ORM order_by；未知字段忽略以保证安全。"""
    for spec in page_request.sort:
        column = _SORTABLE_COLUMNS.get(spec.field)
        if column is None:
            continue
        stmt = stmt.order_by(
            column.desc() if spec.direction == SortDirection.DESC else column.asc()
        )
    # 无显式排序时，按 updated_at 降序保证结果稳定。
    if not page_request.sort:
        stmt = stmt.order_by(ProjectModel.updated_at.desc())
    return stmt
