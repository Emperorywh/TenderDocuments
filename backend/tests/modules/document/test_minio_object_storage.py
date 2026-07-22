"""MinIO 对象存储写入适配器测试（C-002 独立验证）。

本机无真实 MinIO，故以 mock 客户端验证适配器对 SDK 的调用契约；真实 MinIO
集成验证待 Docker 就绪。
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock

import pytest
from minio.error import S3Error

from tender_insight.modules.document.application import ObjectCategory, ObjectKey
from tender_insight.modules.document.infrastructure.minio_object_storage import (
    MinioObjectStorage,
)


def _storage(client: MagicMock) -> MinioObjectStorage:
    return MinioObjectStorage(
        endpoint="minio:9000",
        access_key="ak",
        secret_key="sk",
        bucket="tender",
        client=client,
    )


def test_put_uploads_bytes_with_correct_key_and_content_type() -> None:
    """写入固定字节；put_object 以分类/键路径与 content_type 调用。"""
    client = MagicMock()
    storage = _storage(client)

    key = ObjectKey(category=ObjectCategory.ORIGINAL, key="abc")
    storage.put(key, b"hello", content_type="application/pdf")

    client.put_object.assert_called_once()
    args, kwargs = client.put_object.call_args
    assert args[0] == "tender"
    assert args[1] == "original/abc"
    stream = args[2]
    assert isinstance(stream, BytesIO)
    assert stream.getvalue() == b"hello"
    assert kwargs["length"] == 5
    assert kwargs["content_type"] == "application/pdf"


def test_exists_true_when_object_present() -> None:
    client = MagicMock()
    client.stat_object.return_value = MagicMock()
    storage = _storage(client)

    assert storage.exists(ObjectKey(category=ObjectCategory.PAGES, key="x")) is True
    client.stat_object.assert_called_once_with("tender", "pages/x")


def test_exists_false_on_no_such_key() -> None:
    client = MagicMock()
    client.stat_object.side_effect = S3Error(
        code="NoSuchKey", message="not found", resource="r", request_id="1", host_id="h", response=""
    )
    storage = _storage(client)

    assert storage.exists(ObjectKey(category=ObjectCategory.REPORTS, key="y")) is False


def test_exists_propagates_other_errors() -> None:
    """非 NoSuchKey 的 S3 错误向上抛出，不静默吞掉。"""
    client = MagicMock()
    client.stat_object.side_effect = S3Error(
        code="AccessDenied", message="denied", resource="r", request_id="1", host_id="h", response=""
    )
    storage = _storage(client)

    with pytest.raises(S3Error):
        storage.exists(ObjectKey(category=ObjectCategory.REPORTS, key="z"))
