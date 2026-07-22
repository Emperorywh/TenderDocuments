"""文件类型（魔数）校验（C-010）。

按 SPEC.md 第 6.4、11.1 节，校验扩展名、MIME 与文件魔数（真实签名）一致；
伪扩展名样本被拒绝。首版支持 PDF 与 DOCX（DOCX 为 ZIP 容器，魔数 PK）。

纯逻辑（仅依赖标准库与纯错误类型），可独立测试。
"""

from __future__ import annotations

from enum import StrEnum

from tender_insight.modules.document.domain.exceptions import FileTypeMismatchError


class FileFormat(StrEnum):
    """首版支持的真实文件格式。"""

    PDF = "PDF"
    DOCX = "DOCX"
    UNKNOWN = "UNKNOWN"


# 魔数（文件签名）：格式 -> 起始字节。
_MAGIC_SIGNATURES: dict[FileFormat, bytes] = {
    FileFormat.PDF: b"%PDF-",
    # DOCX/ZIP 容器起始签名；DOCX 是 OOXML（ZIP）。
    FileFormat.DOCX: b"PK\x03\x04",
}

# 格式 -> 允许的 MIME 集合（魔数检测到的格式须与声明 MIME 一致）。
_FORMAT_MIMES: dict[FileFormat, frozenset[str]] = {
    FileFormat.PDF: frozenset({"application/pdf"}),
    FileFormat.DOCX: frozenset(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    ),
}

# 格式 -> 允许的扩展名（不含点）。
_FORMAT_EXTENSIONS: dict[FileFormat, frozenset[str]] = {
    FileFormat.PDF: frozenset({"pdf"}),
    FileFormat.DOCX: frozenset({"docx"}),
}


def detect_format(data: bytes) -> FileFormat:
    """按魔数检测真实格式；未知返回 UNKNOWN。"""
    for fmt, signature in _MAGIC_SIGNATURES.items():
        if data.startswith(signature):
            return fmt
    return FileFormat.UNKNOWN


def validate_file_type(
    data: bytes,
    *,
    declared_mime: str,
    declared_extension: str,
) -> FileFormat:
    """校验声明 MIME/扩展名与魔数一致；不一致抛 FileTypeMismatchError。

    declared_extension 不含前导点（如 "pdf"）。返回检测到的真实格式。
    """
    actual = detect_format(data)
    declared_ext = declared_extension.lower().lstrip(".")
    declared_mime_l = declared_mime.lower().strip()

    if actual == FileFormat.UNKNOWN:
        raise FileTypeMismatchError(
            f"无法识别文件魔数：扩展名 {declared_ext!r}、MIME {declared_mime_l!r}"
        )

    allowed_ext = _FORMAT_EXTENSIONS.get(actual, frozenset())
    allowed_mime = _FORMAT_MIMES.get(actual, frozenset())
    if declared_ext not in allowed_ext or declared_mime_l not in allowed_mime:
        raise FileTypeMismatchError(
            f"文件类型不一致：声明 {declared_ext!r}/{declared_mime_l!r}，"
            f"魔数检测为 {actual.value}"
        )
    return actual
