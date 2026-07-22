"""operation_log API 层（B-018）。

只读分页查询接口，按 project_id/动作筛选，不返回身份字段。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from tender_insight.bootstrap.db import get_session
from tender_insight.modules.operation_log.application.list_operation_logs import (
    OperationLogItem,
    list_operation_logs,
)
from tender_insight.shared.pagination import MAX_PAGE_SIZE, Page, PageRequest


def create_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1/operation-logs", tags=["operation-logs"])

    @router.get("", response_model=Page[OperationLogItem])
    def list_logs(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
        project_id: str | None = Query(default=None),
        action: str | None = Query(default=None),
        resource_type: str | None = Query(default=None),
        resource_id: str | None = Query(default=None),
        session: Session = Depends(get_session),
    ) -> Page[OperationLogItem]:
        """查询操作记录。

        project_id 便捷参数等价于 resource_type=project 且 resource_id=project_id。
        响应不含用户/操作者身份字段。
        """
        rtype = resource_type
        rid = resource_id
        if project_id is not None:
            rtype = "project"
            rid = project_id
        return list_operation_logs(
            session,
            PageRequest(page=page, page_size=page_size),
            resource_type=rtype,
            resource_id=rid,
            action=action,
        )

    return router
