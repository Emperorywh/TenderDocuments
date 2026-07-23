"""稳定错误码目录（纯，无框架依赖）。

将错误码单独置于纯模块，使领域层（state_transitions、各模块 domain 异常）可
安全引用 ErrorCode 取值，而不引入 shared.errors 的 FastAPI 依赖。SPEC.md 第
8.1 节要求错误响应包含稳定 error_code；新增错误必须在此登记。
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """稳定错误码目录。"""

    # 输入与值对象校验。
    INVALID_UUID = "INVALID_UUID"
    NAIVE_BUSINESS_TIME = "NAIVE_BUSINESS_TIME"
    INVALID_MONEY = "INVALID_MONEY"
    INVALID_SCORE = "INVALID_SCORE"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_PROJECT_DATA = "INVALID_PROJECT_DATA"
    UPLOAD_OBJECT_INVALID = "UPLOAD_OBJECT_INVALID"
    FILE_TYPE_MISMATCH = "FILE_TYPE_MISMATCH"
    EMPTY_FILE = "EMPTY_FILE"
    CORRUPT_FILE = "CORRUPT_FILE"
    COMPRESSION_BOMB = "COMPRESSION_BOMB"
    DUPLICATE_FILE = "DUPLICATE_FILE"
    FILE_LIMIT_EXCEEDED = "FILE_LIMIT_EXCEEDED"

    # 资源与并发。
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    PRECONDITION_FAILED = "PRECONDITION_FAILED"

    # 状态机与业务规则。
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    UNPUBLISHABLE = "UNPUBLISHABLE"

    # 异步投递（outbox）。
    OUTBOX_DELIVERY_FAILED = "OUTBOX_DELIVERY_FAILED"

    # 未分类内部错误。
    INTERNAL_ERROR = "INTERNAL_ERROR"
