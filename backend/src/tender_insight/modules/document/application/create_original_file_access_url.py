"""原始文件短期下载地址用例（C-033）。

为已接入的 DocumentVersion 生成原始文件的短期授权下载地址。对象默认私有，
读取只能经后端签发的短期 presigned_get_url（SPEC.md 第 4.2、6.4 节）。

响应只返回短期地址与到期时间，不单独暴露内部对象键：客户端仅凭签名地址访问，
无法获知可用于其它用途的原始对象路径。地址到期由对象存储校验失效。
"""

from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel

from tender_insight.modules.document.application import (
    DocumentVersionRepository,
    ObjectCategory,
    ObjectKey,
    ObjectStorage,
)
from tender_insight.shared.business_time import BusinessInstant, Clock
from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid


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
    ) -> None:
        self._versions = version_repository
        self._storage = object_storage
        self._ttl_seconds = ttl_seconds
        self._clock = clock

    def execute(self, version_id: Uuid) -> OriginalFileAccessUrl:
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
