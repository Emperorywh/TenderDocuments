"""压缩异常（压缩炸弹）校验测试（C-012 独立验证）。

验证超过解压限制的固定样本被拒绝。
"""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from tender_insight.modules.document.domain.compression import validate_compression
from tender_insight.modules.document.domain.exceptions import CompressionBombError


def _make_zip(contents: dict[str, str]) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, body in contents.items():
            zf.writestr(name, body)
    return buf.getvalue()


def test_small_zip_passes() -> None:
    data = _make_zip({"a.txt": "hi"})
    # 允许 1MB 解压、比 100。
    validate_compression(data, max_uncompressed_bytes=1024 * 1024, max_ratio=100)


def test_oversize_uncompressed_rejected() -> None:
    """解压后体积超过上限被拒绝。"""
    big = "x" * 5000
    data = _make_zip({"big.txt": big})
    with pytest.raises(CompressionBombError) as info:
        validate_compression(data, max_uncompressed_bytes=1000, max_ratio=10_000)
    assert "体积" in info.value.detail
    assert info.value.code == "COMPRESSION_BOMB"


def test_high_ratio_rejected() -> None:
    """压缩比异常高（高度可压缩大内容）被拒绝。"""
    # 大量重复字节压缩比极高。
    bomb = _make_zip({"bomb.txt": "\x00" * 200_000})
    with pytest.raises(CompressionBombError) as info:
        validate_compression(
            bomb, max_uncompressed_bytes=10_000_000, max_ratio=50.0
        )
    assert "压缩比" in info.value.detail


def test_non_zip_not_checked() -> None:
    """非 ZIP 容器不做压缩检查（不抛错）。"""
    validate_compression(b"%PDF-1.7\n%%EOF", max_uncompressed_bytes=1, max_ratio=1.0)
