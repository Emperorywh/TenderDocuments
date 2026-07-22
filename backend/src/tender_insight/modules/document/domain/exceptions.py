"""document 领域异常（纯领域层）。"""

from __future__ import annotations

from tender_insight.shared.domain_error import DomainError
from tender_insight.shared.error_codes import ErrorCode


class UploadObjectError(DomainError):
    """上传完成时对象校验失败（缺失或大小不符）。

    code 默认 UPLOAD_OBJECT_INVALID；可在构造时指定更细分的码。
    """

    code = ErrorCode.UPLOAD_OBJECT_INVALID.value
    http_status = 400
    title = "上传对象校验失败"


class FileTypeMismatchError(DomainError):
    """文件类型（扩展名/MIME/魔数）不一致时抛出。"""

    code = ErrorCode.FILE_TYPE_MISMATCH.value
    http_status = 400
    title = "文件类型不一致"
