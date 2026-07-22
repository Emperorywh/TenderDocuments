"""上传完成对象校验测试（C-009 独立验证）。

验证对象缺失或大小不符时抛错（不创建业务文件，由完成用例 C-017 保证）。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tender_insight.modules.document.application.upload_verification import (
    verify_uploaded_object,
)
from tender_insight.modules.document.domain.exceptions import UploadObjectError


def _storage(*, exists: bool = True, size: int = 100) -> MagicMock:
    storage = MagicMock()
    storage.exists.return_value = exists
    storage.size.return_value = size
    return storage


def test_valid_object_returns_size() -> None:
    storage = _storage(exists=True, size=2048)
    actual = verify_uploaded_object(storage, "quarantine/abc", 2048)
    assert actual == 2048


def test_missing_object_raises() -> None:
    storage = _storage(exists=False)
    with pytest.raises(UploadObjectError) as info:
        verify_uploaded_object(storage, "quarantine/abc", 100)
    assert "缺失" in info.value.detail


def test_size_mismatch_raises() -> None:
    storage = _storage(exists=True, size=50)
    with pytest.raises(UploadObjectError) as info:
        verify_uploaded_object(storage, "quarantine/abc", 100)
    assert "大小不符" in info.value.detail


def test_invalid_object_key_raises() -> None:
    storage = _storage()
    with pytest.raises(UploadObjectError):
        verify_uploaded_object(storage, "no-slash-key", 100)


def test_error_has_stable_code() -> None:
    storage = _storage(exists=False)
    with pytest.raises(UploadObjectError) as info:
        verify_uploaded_object(storage, "quarantine/abc", 100)
    assert info.value.code == "UPLOAD_OBJECT_INVALID"
