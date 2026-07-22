"""文件类型（魔数）校验测试（C-010 独立验证）。

验证伪扩展名固定样本被拒绝，真实样本通过。
"""

from __future__ import annotations

import pytest

from tender_insight.modules.document.domain.exceptions import FileTypeMismatchError
from tender_insight.modules.document.domain.file_type import (
    FileFormat,
    detect_format,
    validate_file_type,
)

# 真实样本的魔数前缀（足以识别格式）。
_PDF_BYTES = b"%PDF-1.7\n...rest of pdf..."
_DOCX_BYTES = b"PK\x03\x04\x14\x00\x06\x00\x08\x00...zip docx..."
# 伪装样本：内容是 ZIP 但声明为 PDF。
_FAKE_PDF = b"PK\x03\x04zip-content"


def test_detect_pdf_and_docx() -> None:
    assert detect_format(_PDF_BYTES) == FileFormat.PDF
    assert detect_format(_DOCX_BYTES) == FileFormat.DOCX
    assert detect_format(b"random") == FileFormat.UNKNOWN


def test_validate_pdf_succeeds() -> None:
    fmt = validate_file_type(
        _PDF_BYTES, declared_mime="application/pdf", declared_extension="pdf"
    )
    assert fmt == FileFormat.PDF


def test_validate_docx_succeeds() -> None:
    fmt = validate_file_type(
        _DOCX_BYTES,
        declared_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        declared_extension="docx",
    )
    assert fmt == FileFormat.DOCX


def test_fake_extension_rejected() -> None:
    """内容为 ZIP 却声明 PDF 被拒绝（伪扩展名）。"""
    with pytest.raises(FileTypeMismatchError):
        validate_file_type(
            _FAKE_PDF, declared_mime="application/pdf", declared_extension="pdf"
        )


def test_unknown_magic_rejected() -> None:
    with pytest.raises(FileTypeMismatchError):
        validate_file_type(
            b"plain text", declared_mime="application/pdf", declared_extension="pdf"
        )


def test_mime_extension_inconsistent_rejected() -> None:
    """PDF 内容但扩展名 docx 被拒绝。"""
    with pytest.raises(FileTypeMismatchError):
        validate_file_type(
            _PDF_BYTES,
            declared_mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            declared_extension="docx",
        )


def test_extension_with_dot_normalized() -> None:
    """扩展名带点也能识别。"""
    fmt = validate_file_type(
        _PDF_BYTES, declared_mime="application/pdf", declared_extension=".pdf"
    )
    assert fmt == FileFormat.PDF
