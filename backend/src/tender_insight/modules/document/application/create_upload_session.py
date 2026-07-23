"""创建上传会话应用用例（C-007，C-030 接入操作记录）。

按 SPEC.md 第 8.3 节上传流程的起始：校验项目存在与部署字节上限，创建 PENDING
上传会话（暂存对象键在 quarantine 分区、不可猜测），返回短期预签名上传地址与
会话标识。客户端据此直传对象存储。

上传属关键操作（SPEC.md 第 6.2 节），每个命令恰好产生一条操作记录。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from pydantic import BaseModel, Field

from tender_insight.modules.document.application import (
    ObjectCategory,
    ObjectKey,
    ObjectStorage,
    UploadSessionRepository,
)
from tender_insight.modules.document.domain.upload_session import UploadSession
from tender_insight.modules.operation_log.application import OperationRecorder
from tender_insight.modules.operation_log.application.recording import record_command_outcome
from tender_insight.shared.business_time import BusinessInstant, Clock
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.request_context import current_request_context


class CreateUploadSessionCommand(BaseModel):
    project_id: str
    declared_filename: str = Field(min_length=1)
    declared_size_bytes: int = Field(gt=0)
    declared_mime: str = Field(min_length=1)


class UploadInfo(BaseModel):
    """返回给客户端的短期上传信息。"""

    session_id: str
    object_key: str
    upload_url: str
    expires_at: str  # ISO 字符串
    method: str = "PUT"


class CreateUploadSessionUseCase:
    def __init__(
        self,
        *,
        repository: UploadSessionRepository,
        session,
        object_storage: ObjectStorage,
        project_exists: Callable[[Uuid], bool],
        max_file_bytes: int,
        session_ttl_seconds: int = 900,
        clock: Clock | None = None,
        session_factory: Callable[[], object] | None = None,
        open_recorder: Callable[[object], OperationRecorder] | None = None,
    ) -> None:
        self._repository = repository
        self._session = session
        self._object_storage = object_storage
        self._project_exists = project_exists
        self._max_file_bytes = max_file_bytes
        self._session_ttl_seconds = session_ttl_seconds
        self._clock = clock
        self._session_factory = session_factory
        self._open_recorder = open_recorder

    def execute(self, command: CreateUploadSessionCommand) -> UploadInfo:
        project_id = Uuid.from_str(command.project_id)
        ctx = current_request_context()

        def perform() -> UploadInfo:
            if not self._project_exists(project_id):
                raise NotFoundError(f"项目不存在：{command.project_id}")
            # 部署字节上限（强类型配置，非魔法常量）。
            if command.declared_size_bytes > self._max_file_bytes:
                raise ValueError(
                    f"声明大小 {command.declared_size_bytes} 超过上限 {self._max_file_bytes}"
                )

            now = BusinessInstant.now(clock=self._clock).value
            expires_at = now + timedelta(seconds=self._session_ttl_seconds)
            # 暂存键：quarantine 分区 + 不可猜测 UUID 字符串，不含原始文件名。
            object_key = ObjectKey(category=ObjectCategory.QUARANTINE, key=str(Uuid.new()))

            upload_session = UploadSession.create(
                project_id=project_id,
                declared_filename=command.declared_filename,
                declared_size_bytes=command.declared_size_bytes,
                declared_mime=command.declared_mime,
                object_key=object_key.as_path(),
                created_at=now,
                expires_at=expires_at,
            )
            self._repository.add(upload_session)

            upload_url = self._object_storage.presigned_put_url(
                object_key, expires_in_seconds=self._session_ttl_seconds
            )
            return UploadInfo(
                session_id=str(upload_session.id),
                object_key=object_key.as_path(),
                upload_url=upload_url,
                expires_at=expires_at.isoformat(),
            )

        return record_command_outcome(
            session=self._session,
            session_factory=self._session_factory,  # type: ignore[arg-type]
            open_recorder=self._open_recorder,  # type: ignore[arg-type]
            action="document.upload.create",
            resource_type="project",
            resource_id=str(project_id),
            request_id=ctx.request_id if ctx is not None else None,
            perform=perform,
        )
