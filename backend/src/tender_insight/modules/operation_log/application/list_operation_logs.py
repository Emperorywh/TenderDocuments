"""操作记录只读查询（B-018）。

分页查询操作记录，支持按资源类型/ID 与动作筛选。只读，不写表。返回项不含任何
身份字段（无虚构操作者），符合 SPEC.md 第 6.2、15.1 节。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tender_insight.modules.operation_log.infrastructure.models import OperationLogModel
from tender_insight.shared.pagination import Page, PageRequest


class OperationLogItem(BaseModel):
    """操作记录列表项（无身份字段）。"""

    id: str
    request_id: str | None
    action: str
    resource_type: str
    resource_id: str
    result: str
    error_code: str | None
    occurred_at: datetime

    # 显式声明：不含 operator/user/identity 字段（防误加）。
    model_config = {"extra": "forbid"}


def list_operation_logs(
    session: Session,
    page_request: PageRequest,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
    action: str | None = None,
) -> Page[OperationLogItem]:
    """分页查询操作记录；按 resource_type/resource_id/action 可选筛选。"""
    filters = []
    if resource_type is not None:
        filters.append(OperationLogModel.resource_type == resource_type)
    if resource_id is not None:
        filters.append(OperationLogModel.resource_id == resource_id)
    if action is not None:
        filters.append(OperationLogModel.action == action)

    base = select(OperationLogModel)
    count_stmt = select(func.count()).select_from(OperationLogModel)
    for f in filters:
        base = base.where(f)
        count_stmt = count_stmt.where(f)

    total = session.scalar(count_stmt) or 0
    stmt = base.order_by(OperationLogModel.occurred_at.desc()).offset(page_request.offset).limit(
        page_request.page_size
    )
    rows = session.execute(stmt).scalars().all()
    items = [
        OperationLogItem(
            id=str(row.id),
            request_id=row.request_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            result=row.result,
            error_code=row.error_code,
            occurred_at=row.occurred_at,
        )
        for row in rows
    ]
    return Page(items=items, total=total, page=page_request.page, page_size=page_request.page_size)
