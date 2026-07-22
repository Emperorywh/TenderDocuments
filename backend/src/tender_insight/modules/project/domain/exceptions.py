"""project 领域异常（纯领域层）。

继承纯 DomainError，使 API 层可统一映射为 Problem Details，而领域层不依赖框架。
"""

from __future__ import annotations

from tender_insight.shared.domain_error import DomainError
from tender_insight.shared.error_codes import ErrorCode


class InvalidProjectDataError(DomainError):
    """项目数据非法（空名称、缺失地区/行业/类型等）时抛出的稳定错误。"""

    code = ErrorCode.INVALID_PROJECT_DATA.value
    http_status = 400
    title = "项目数据非法"
