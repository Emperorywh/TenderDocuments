"""原始文件短期下载地址用例（C-033，C-030 接入操作记录）。

为已接入的 DocumentVersion 生成原始文件的短期授权下载地址。对象默认私有，
读取只能经后端签发的短期 presigned_get_url（SPEC.md 第 4.2、6.4 节）。

响应只返回短期地址与到期时间，不单独暴露内部对象键：客户端仅凭签名地址访问，
无法获知可用于其它用途的原始对象路径。地址到期由对象存储校验失效。

下载属关键操作（SPEC.md 第 6.2 节），每次签发恰好产生一条操作记录。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from pydantic import BaseModel

from tender_insight.modules.document.application import (
    DocumentVersionRepository,
    ObjectCategory,
    ObjectKey,
    ObjectStorage,
)
from tender_insight.modules.operation_log.application import OperationRecorder
from tender_insight.modules.operation_log.application.recording import record_command_outcome
from tender_insight.shared.business_time import BusinessInstant, Clock
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.request_context import current_request_context


class OriginalFileAccessUrl(BaseModel):
    """原始文件短期下载地址。

    刻意不含 object_key 字段：客户端只应通过签名地址访问，不接触内部对象键。
    """

    download_url: str
    expires_at: str  # ISO 字符串
    method: str = "GET"


def _parse_object_key(object_key: str) -> ObjectKey:
    """解析存储内路径 'category/key' 为 ObjectKey。"""
    parts = object_key.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"非法对象键：{object_key}")
    return ObjectKey(category=ObjectCategory(parts[0]), key=parts[1])


class CreateOriginalFileAccessUrlUseCase:
    def __init__(
        self,
        *,
        version_repository: DocumentVersionRepository,
        object_storage: ObjectStorage,
        ttl_seconds: int = 900,
        clock: Clock | None = None,
        session=None,
        session_factory: Callable[[], object] | None = None,
        open_recorder: Callable[[object], OperationRecorder] | None = None,
    ) -> None:
        self._versions = version_repository
        self._storage = object_storage
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._session = session
        self._session_factory = session_factory
        self._open_recorder = open_recorder

    def execute(self, version_id: Uuid) -> OriginalFileAccessUrl:
        ctx = current_request_context()

        def perform() -> OriginalFileAccessUrl:
            version = self._versions.get(version_id)
            if version is None:
                raise NotFoundError(f"文件版本不存在：{version_id}")
            # 原始对象键由系统生成（不可猜测 UUID），客户端只得到签名后的下载地址。
            key = _parse_object_key(version.original_object_key)
            now = BusinessInstant.now(clock=self._clock).value
            expires_at = now + timedelta(seconds=self._ttl_seconds)
            download_url = self._storage.presigned_get_url(
                key, expires_in_seconds=self._ttl_seconds
            )
            return OriginalFileAccessUrl(
                download_url=download_url,
                expires_at=expires_at.isoformat(),
            )

        # 下载为只读操作；未注入会话时仅返回结果（不记录）。
        if self._session is None:
            return perform()
        return record_command_outcome(
            session=self._session,
            session_factory=self._session_factory,  # type: ignore[arg-type]
            open_recorder=self._open_recorder,  # type: ignore[arg-type]
            action="document.download",
            resource_type="document_version",
            resource_id=str(version_id),
            request_id=ctx.request_id if ctx is not None else None,
            perform=perform,
        )
