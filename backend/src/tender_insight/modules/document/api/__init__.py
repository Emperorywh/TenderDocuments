"""document 模块 API 层（C-008 起）。

只做协议转换，不承载业务规则。上传会话创建经用例编排。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from tender_insight.bootstrap.config import get_settings
from tender_insight.bootstrap.db import get_object_storage, get_session
from tender_insight.modules.document.application import ObjectStorage
from tender_insight.modules.document.application.create_upload_session import (
    CreateUploadSessionCommand,
    CreateUploadSessionUseCase,
    UploadInfo,
)
from tender_insight.modules.document.application.list_documents import (
    DocumentListItem,
    list_documents,
)
from tender_insight.modules.document.infrastructure.upload_session_repository import (
    SqlAlchemyUploadSessionRepository,
)
from tender_insight.modules.project.infrastructure.repository import (
    SqlAlchemyProjectRepository,
)
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.pagination import MAX_PAGE_SIZE, Page, PageRequest


def create_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["documents"])

    @router.post(
        "/upload-sessions",
        response_model=UploadInfo,
        status_code=status.HTTP_201_CREATED,
    )
    def create_upload_session(
        command: CreateUploadSessionCommand,
        session: Session = Depends(get_session),
        object_storage: ObjectStorage = Depends(get_object_storage),  # type: ignore[assignment]
    ) -> UploadInfo:
        """创建上传会话，返回短期预签名上传地址。

        请求与响应均不含身份字段；缺字段 422、未知项目 404、超限 400。
        """
        project_repo = SqlAlchemyProjectRepository(session)

        def _project_exists(pid: Uuid) -> bool:
            return project_repo.get(pid) is not None

        settings = get_settings()
        use_case = CreateUploadSessionUseCase(
            repository=SqlAlchemyUploadSessionRepository(session),
            session=session,
            object_storage=object_storage,
            project_exists=_project_exists,
            max_file_bytes=settings.max_file_bytes,
            session_ttl_seconds=settings.presigned_url_ttl_seconds,
        )
        return use_case.execute(command)

    @router.get(
        "/projects/{project_id}/documents",
        response_model=Page[DocumentListItem],
    )
    def list_project_documents(
        project_id: str,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
        session: Session = Depends(get_session),
    ) -> Page[DocumentListItem]:
        """分页查询项目下的逻辑文件（含版本数与确认状态）。"""
        return list_documents(
            session,
            Uuid.from_str(project_id),
            PageRequest(page=page, page_size=page_size),
        )

    return router
