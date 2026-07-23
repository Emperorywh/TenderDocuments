"""analysis 领域异常（纯领域层）。

D-014：任务归属不一致错误。Worker 校验任务、运行、项目的关联，发现消息中的 ID 与
数据库权威不一致时抛出，拒绝执行伪造或不一致的消息（SPEC.md 第 4.3 节）。
"""

from __future__ import annotations

from tender_insight.shared.domain_error import DomainError
from tender_insight.shared.error_codes import ErrorCode


class TaskOwnershipError(DomainError):
    """任务-运行-项目归属不一致（消息声称的 ID 与数据库权威不符）。

    SPEC.md 第 4.3 节要求 Worker 不信任消息中的孤立 ID；本错误表示校验未通过，
    调用方应拒绝执行该消息（不领取、不产出结果）。
    """

    code = ErrorCode.TASK_OWNERSHIP_MISMATCH.value
    http_status = 422
    title = "任务归属不一致"
