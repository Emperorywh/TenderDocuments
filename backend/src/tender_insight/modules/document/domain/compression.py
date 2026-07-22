"""压缩异常（压缩炸弹）校验（C-012）。

按 SPEC.md 第 11.1 节，对 ZIP 容器（DOCX）检查解压后总字节数与压缩比，超过
部署限制则拒绝，防止压缩炸弹耗尽资源。纯逻辑，可独立测试。
"""

from __future__ import annotations

import zipfile
from io import BytesIO

from tender_insight.modules.document.domain.exceptions import CompressionBombError
from tender_insight.modules.document.domain.file_type import FileFormat, detect_format


def validate_compression(
    data: bytes,
    *,
    max_uncompressed_bytes: int,
    max_ratio: float,
) -> None:
    """校验压缩容器是否疑似炸弹。

    非 ZIP 容器不做压缩检查。超过解压体积上限或压缩比上限抛 CompressionBombError。
    """
    if detect_format(data) != FileFormat.DOCX:
        return

    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            total_uncompressed = sum(info.file_size for info in zf.infolist())
    except zipfile.BadZipFile as cause:
        # 损坏归 CorruptFileError（C-011）；此处统一向上抛压缩异常口径。
        raise CompressionBombError("ZIP 容器无法读取") from cause

    if total_uncompressed > max_uncompressed_bytes:
        raise CompressionBombError(
            f"解压后体积 {total_uncompressed} 超过上限 {max_uncompressed_bytes}"
        )

    if len(data) > 0:
        ratio = total_uncompressed / len(data)
        if ratio > max_ratio:
            raise CompressionBombError(
                f"压缩比 {ratio:.1f} 超过上限 {max_ratio:.1f}"
            )
