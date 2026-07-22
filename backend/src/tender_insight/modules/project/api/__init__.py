"""project 模块 API 层（B-005 起）。

只做协议转换：解析请求为命令、组装用例依赖（仓储+会话）、调用用例并返回结果。
不承载业务规则。路由以独立 APIRouter 暴露，由主应用挂载到 /api/v1 前缀下。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
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
from tender_insight.modules.project.infrastructure.repository import (
    SqlAlchemyProjectRepository,
)


class EditProjectRequest(BaseModel):
    """编辑请求体：project_id 取自路径，body 仅含版本号与可变字段。"""

    expected_version: int = Field(ge=1)
    name: str | None = None
    region: str | None = None
    industry: str | None = None
    project_type: str | None = None


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
