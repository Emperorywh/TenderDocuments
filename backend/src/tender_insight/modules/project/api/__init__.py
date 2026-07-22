"""project 模块 API 层（B-005 起）。

只做协议转换：解析请求为命令、组装用例依赖（仓储+会话）、调用用例并返回结果。
不承载业务规则。路由以独立 APIRouter 暴露，由主应用挂载到 /api/v1 前缀下。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tender_insight.bootstrap.db import get_session
from tender_insight.modules.project.application.create_project import (
    CreateProjectCommand,
    CreateProjectResult,
    CreateProjectUseCase,
)
from tender_insight.modules.project.application.edit_project import (
    EditProjectCommand,
    EditProjectResult,
    EditProjectUseCase,
)
from tender_insight.modules.project.application.list_projects import (
    ProjectListItem,
    list_projects,
)
from tender_insight.modules.project.infrastructure.repository import (
    SqlAlchemyProjectRepository,
)
from tender_insight.shared.pagination import (
    MAX_PAGE_SIZE,
    Page,
    PageRequest,
    SortDirection,
    SortField,
)
from tender_insight.shared.states import ProjectLifecycleStatus


class EditProjectRequest(BaseModel):
    """编辑请求体：project_id 取自路径，body 仅含版本号与可变字段。"""

    expected_version: int = Field(ge=1)
    name: str | None = None
    region: str | None = None
    industry: str | None = None
    project_type: str | None = None


def _parse_sort(sort_params: list[str]) -> list[SortField]:
    """把 "field" 或 "field:desc" 形式的查询参数解析为 SortField。"""
    fields: list[SortField] = []
    for raw in sort_params:
        if not raw:
            continue
        parts = raw.split(":")
        field_name = parts[0]
        is_desc = len(parts) > 1 and parts[1] == "desc"
        direction = SortDirection.DESC if is_desc else SortDirection.ASC
        fields.append(SortField(field=field_name, direction=direction))
    return fields


def _build_page_request(
    page: int,
    page_size: int,
    sort: list[str],
) -> PageRequest:
    """构造分页请求；page_size 越界由 Pydantic 校验拒绝（422）。"""
    return PageRequest(page=page, page_size=page_size, sort=_parse_sort(sort))


def create_router() -> APIRouter:
    """构造 projects 路由。"""
    router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

    @router.post(
        "",
        response_model=CreateProjectResult,
        status_code=status.HTTP_201_CREATED,
    )
    def create_project(
        command: CreateProjectCommand,
        session: Session = Depends(get_session),
    ) -> CreateProjectResult:
        """创建项目。

        必填字段缺失返回 422 VALIDATION_ERROR；空白字段被领域拒绝返回
        400 INVALID_PROJECT_DATA（统一 Problem Details）。
        """
        repository = SqlAlchemyProjectRepository(session)
        return CreateProjectUseCase(repository, session).execute(command)

    @router.get("", response_model=Page[ProjectListItem])
    def list_projects_route(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
        sort: list[str] | None = Query(default=None),
        status_filter: str | None = Query(None, alias="status"),
        session: Session = Depends(get_session),
    ) -> Page[ProjectListItem]:
        """分页查询项目。

        page_size 超过上限返回 422；status 缺省时仅返回活动项目，传入
        ARCHIVED 等可列出对应状态。
        """
        page_request = _build_page_request(page, page_size, sort or [])
        states = (
            frozenset({ProjectLifecycleStatus(status_filter)})
            if status_filter is not None
            else None
        )
        return list_projects(session, page_request, states=states)

    @router.patch(
        "/{project_id}",
        response_model=EditProjectResult,
    )
    def edit_project(
        project_id: str,
        body: EditProjectRequest,
        session: Session = Depends(get_session),
    ) -> EditProjectResult:
        """编辑项目（乐观并发）。

        版本冲突返回 409 CONFLICT；项目不存在返回 404 NOT_FOUND；
        空白字段返回 400 INVALID_PROJECT_DATA（统一 Problem Details）。
        """
        command = EditProjectCommand(
            project_id=project_id,
            expected_version=body.expected_version,
            name=body.name,
            region=body.region,
            industry=body.industry,
            project_type=body.project_type,
        )
        repository = SqlAlchemyProjectRepository(session)
        return EditProjectUseCase(repository, session).execute(command)

    return router
