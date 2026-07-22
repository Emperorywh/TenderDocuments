"""文件可读性校验测试（C-011 独立验证）。

验证空文件与损坏样本得到不同稳定错误码。
"""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from tender_insight.modules.document.domain.exceptions import (
    CorruptFileError,
    EmptyFileError,
)
from tender_insight.modules.document.domain.file_integrity import validate_file_integrity


def _make_zip() -> bytes:
    """构造一个合法的小 ZIP。"""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.txt", "hello")
    return buf.getvalue()


def test_empty_file_raises_empty_error() -> None:
    with pytest.raises(EmptyFileError) as info:
        validate_file_integrity(b"")
    assert info.value.code == "EMPTY_FILE"


def test_valid_pdf_and_zip_pass() -> None:
    validate_file_integrity(b"%PDF-1.7\n...content...\n%%EOF")
    validate_file_integrity(_make_zip())


def test_truncated_pdf_raises_corrupt_error() -> None:
    """PDF 仅有头部、缺少结束标记，判为损坏。"""
    with pytest.raises(CorruptFileError) as info:
        validate_file_integrity(b"%PDF-1.7\nbroken")
    assert info.value.code == "CORRUPT_FILE"


def test_corrupt_zip_raises_corrupt_error() -> None:
    """ZIP 魔数但中央目录损坏。"""
    corrupt = b"PK\x03\x04" + b"\x00" * 50 + b"garbage"
    with pytest.raises(CorruptFileError) as info:
        validate_file_integrity(corrupt)
    assert info.value.code == "CORRUPT_FILE"


def test_empty_and_corrupt_have_distinct_codes() -> None:
    """空文件与损坏文件错误码不同。"""
    codes: set[str] = set()
    for sample in (b"", b"%PDF-1.7\nbroken"):
        try:
            validate_file_integrity(sample)
        except (EmptyFileError, CorruptFileError) as exc:
            codes.add(exc.code)
    assert codes == {"EMPTY_FILE", "CORRUPT_FILE"}
