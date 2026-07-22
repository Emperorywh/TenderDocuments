"""文件可读性（空/损坏）校验（C-011）。

按 SPEC.md 第 11.1 节，空文件与损坏文件得到**不同稳定错误码**（EMPTY_FILE /
CORRUPT_FILE），便于前端精确反馈。纯逻辑，可独立测试。
"""

from __future__ import annotations

import zipfile
from io import BytesIO

from tender_insight.modules.document.domain.exceptions import (
    CorruptFileError,
    EmptyFileError,
)
from tender_insight.modules.document.domain.file_type import FileFormat, detect_format


def validate_file_integrity(data: bytes) -> None:
    """校验文件可读性：空文件抛 EmptyFileError，结构损坏抛 CorruptFileError。"""
    if len(data) == 0:
        raise EmptyFileError("文件为空（0 字节）")

    fmt = detect_format(data)
    if fmt == FileFormat.PDF:
        _check_pdf_integrity(data)
    elif fmt == FileFormat.DOCX:
        _check_zip_integrity(data)
    # UNKNOWN：类型识别留给文件类型校验（C-010），完整性不额外判断。


def _check_pdf_integrity(data: bytes) -> None:
    """PDF 最小结构校验：须含结束标记 %%EOF。"""
    # 真实 PDF 末尾含 %%EOF；仅头部 %PDF- 而无结束标记视为损坏。
    tail = data[-1024:] if len(data) > 1024 else data
    if b"%%EOF" not in tail:
        raise CorruptFileError("PDF 缺少结束标记 %%EOF")


def _check_zip_integrity(data: bytes) -> None:
    """DOCX/ZIP 容器完整性校验：zipfile 能正确读取中央目录。"""
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            bad = zf.testzip()
    except zipfile.BadZipFile as cause:
        raise CorruptFileError("ZIP 容器损坏，无法读取") from cause
    if bad is not None:
        raise CorruptFileError(f"ZIP 内存在损坏条目：{bad}")
