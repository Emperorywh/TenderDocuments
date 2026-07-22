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


class EmptyFileError(DomainError):
    """空文件（0 字节）时抛出。"""

    code = ErrorCode.EMPTY_FILE.value
    http_status = 400
    title = "空文件"


class CorruptFileError(DomainError):
    """损坏或不可读文件时抛出（结构校验失败）。"""

    code = ErrorCode.CORRUPT_FILE.value
    http_status = 400
    title = "损坏文件"


class CompressionBombError(DomainError):
    """压缩异常（解压后体积或压缩比超限，疑似压缩炸弹）时抛出。"""

    code = ErrorCode.COMPRESSION_BOMB.value
    http_status = 400
    title = "压缩异常"


class DuplicateFileError(DomainError):
    """同项目内已存在相同哈希的文件时抛出（不重复创建版本）。"""

    code = ErrorCode.DUPLICATE_FILE.value
    http_status = 409
    title = "重复文件"


class FileLimitExceededError(DomainError):
    """超出部署文件限额（大小/数量/总字节）时抛出。"""

    code = ErrorCode.FILE_LIMIT_EXCEEDED.value
    http_status = 400
    title = "文件限额超限"
