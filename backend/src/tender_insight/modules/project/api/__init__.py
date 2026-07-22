"""project 模块 API 层（B-005 起）。

只做协议转换：解析请求为命令、组装用例依赖（仓储+会话）、调用用例并返回结果。
不承载业务规则。路由以独立 APIRouter 暴露，由主应用挂载到 /api/v1 前缀下。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from tender_insight.bootstrap.db import get_session
from tender_insight.modules.project.application.create_project import (
    CreateProjectCommand,
    CreateProjectResult,
    CreateProjectUseCase,
)
from tender_insight.modules.project.infrastructure.repository import (
    SqlAlchemyProjectRepository,
)


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

    return router
