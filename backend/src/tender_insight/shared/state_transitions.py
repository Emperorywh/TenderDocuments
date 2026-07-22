"""状态转换通用验证器（A-022）。

在 A-021 的集中状态目录之上，集中维护每个状态机的合法转换边，并提供
``validate_transition`` 校验入口。合法转换静默通过，非法转换抛出稳定错误
``InvalidTransitionError``（error_code = INVALID_STATE_TRANSITION）。

本模块刻意保持纯（仅依赖标准库与 shared.states），使领域层实体可安全调用，
不引入 Web/ORM/框架依赖。API 层（shared.errors）的异常处理器会捕获本错误并
映射为 409 Problem Details。
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from tender_insight.shared.domain_error import DomainError
from tender_insight.shared.error_codes import ErrorCode
from tender_insight.shared.states import (
    AnalysisRunStatus,
    AnalysisTaskStatus,
    DocumentVersionStatus,
    PageStatus,
    ProjectLifecycleStatus,
    ReportSnapshotStatus,
    ReviewStatus,
    UploadSessionStatus,
)


class InvalidTransitionError(DomainError):
    """状态转换非法时抛出的稳定错误。

    继承纯 DomainError，code=INVALID_STATE_TRANSITION，http_status=409；由 shared.errors
    处理器统一映射为 Problem Details。
    """

    code = ErrorCode.INVALID_STATE_TRANSITION.value
    http_status = 409
    title = "非法状态转换"


# 各状态机的合法转换表：当前状态 -> 允许的目标状态集合。
# 依据 SPEC.md 第 5.2～5.5、6.16 节。AnalysisRunCompleteness 为派生字段，
# 不参与显式转换，故不在表中。
_TRANSITIONS: Mapping[type[StrEnum], Mapping[StrEnum, frozenset[StrEnum]]] = {
    # 文件接入：UPLOADING → STORED → VALIDATING → READY → PROCESSING → PROCESSED，
    # 各阶段可进入对应异常终态。
    DocumentVersionStatus: {
        DocumentVersionStatus.UPLOADING: frozenset(
            {DocumentVersionStatus.STORED, DocumentVersionStatus.UPLOAD_FAILED}
        ),
        DocumentVersionStatus.STORED: frozenset(
            {DocumentVersionStatus.VALIDATING, DocumentVersionStatus.REJECTED}
        ),
        DocumentVersionStatus.VALIDATING: frozenset(
            {DocumentVersionStatus.READY, DocumentVersionStatus.REJECTED}
        ),
        DocumentVersionStatus.READY: frozenset({DocumentVersionStatus.PROCESSING}),
        DocumentVersionStatus.PROCESSING: frozenset(
            {DocumentVersionStatus.PROCESSED, DocumentVersionStatus.PROCESSING_FAILED}
        ),
    },
    # 页面解析：原生优先，质量不足走 OCR，任一步可失败。
    PageStatus: {
        PageStatus.PENDING: frozenset(
            {PageStatus.NATIVE_TEXT_READY, PageStatus.OCR_REQUIRED, PageStatus.FAILED}
        ),
        PageStatus.OCR_REQUIRED: frozenset({PageStatus.OCR_READY, PageStatus.FAILED}),
    },
    # 分析运行：主路径至 PUBLISHED；活动状态可请求取消或失败；PUBLISHED 可过期。
    AnalysisRunStatus: {
        AnalysisRunStatus.DRAFT: frozenset({
            AnalysisRunStatus.QUEUED,
            AnalysisRunStatus.CANCEL_REQUESTED,
            AnalysisRunStatus.FAILED,
        }),
        AnalysisRunStatus.QUEUED: frozenset({
            AnalysisRunStatus.PARSING,
            AnalysisRunStatus.CANCEL_REQUESTED,
            AnalysisRunStatus.FAILED,
        }),
        AnalysisRunStatus.PARSING: frozenset({
            AnalysisRunStatus.EXTRACTING,
            AnalysisRunStatus.CANCEL_REQUESTED,
            AnalysisRunStatus.FAILED,
        }),
        AnalysisRunStatus.EXTRACTING: frozenset({
            AnalysisRunStatus.ANALYZING,
            AnalysisRunStatus.CANCEL_REQUESTED,
            AnalysisRunStatus.FAILED,
        }),
        AnalysisRunStatus.ANALYZING: frozenset({
            AnalysisRunStatus.VERIFYING,
            AnalysisRunStatus.CANCEL_REQUESTED,
            AnalysisRunStatus.FAILED,
        }),
        AnalysisRunStatus.VERIFYING: frozenset({
            AnalysisRunStatus.REVIEW_REQUIRED,
            AnalysisRunStatus.READY,
            AnalysisRunStatus.CANCEL_REQUESTED,
            AnalysisRunStatus.FAILED,
        }),
        AnalysisRunStatus.REVIEW_REQUIRED: frozenset({
            AnalysisRunStatus.READY,
            AnalysisRunStatus.CANCEL_REQUESTED,
            AnalysisRunStatus.FAILED,
        }),
        AnalysisRunStatus.READY: frozenset({
            AnalysisRunStatus.PUBLISHED,
            AnalysisRunStatus.CANCEL_REQUESTED,
            AnalysisRunStatus.FAILED,
        }),
        AnalysisRunStatus.CANCEL_REQUESTED: frozenset({AnalysisRunStatus.CANCELLED}),
        AnalysisRunStatus.PUBLISHED: frozenset({AnalysisRunStatus.OUTDATED}),
    },
    # 任务：PENDING → DISPATCHED → RUNNING → SUCCEEDED；可重试、失败、取消。
    AnalysisTaskStatus: {
        AnalysisTaskStatus.PENDING: frozenset(
            {AnalysisTaskStatus.DISPATCHED, AnalysisTaskStatus.CANCELLED}
        ),
        AnalysisTaskStatus.DISPATCHED: frozenset(
            {AnalysisTaskStatus.RUNNING, AnalysisTaskStatus.CANCELLED, AnalysisTaskStatus.FAILED}
        ),
        AnalysisTaskStatus.RUNNING: frozenset(
            {
                AnalysisTaskStatus.SUCCEEDED,
                AnalysisTaskStatus.RETRY_SCHEDULED,
                AnalysisTaskStatus.FAILED,
                AnalysisTaskStatus.CANCELLED,
            }
        ),
        AnalysisTaskStatus.RETRY_SCHEDULED: frozenset(
            {AnalysisTaskStatus.DISPATCHED, AnalysisTaskStatus.FAILED, AnalysisTaskStatus.CANCELLED}
        ),
    },
    # 风险复核：DETECTED → NEEDS_REVIEW → CONFIRMED/MODIFIED/REJECTED → RESOLVED。
    ReviewStatus: {
        ReviewStatus.DETECTED: frozenset({ReviewStatus.NEEDS_REVIEW}),
        ReviewStatus.NEEDS_REVIEW: frozenset(
            {ReviewStatus.CONFIRMED, ReviewStatus.MODIFIED, ReviewStatus.REJECTED}
        ),
        ReviewStatus.CONFIRMED: frozenset({ReviewStatus.RESOLVED}),
        ReviewStatus.MODIFIED: frozenset({ReviewStatus.RESOLVED}),
        ReviewStatus.REJECTED: frozenset({ReviewStatus.RESOLVED}),
    },
    # 报告快照：生成 → 可用/失败；可用 → 过期。
    ReportSnapshotStatus: {
        ReportSnapshotStatus.GENERATING: frozenset(
            {ReportSnapshotStatus.AVAILABLE, ReportSnapshotStatus.FAILED}
        ),
        ReportSnapshotStatus.AVAILABLE: frozenset({ReportSnapshotStatus.OUTDATED}),
    },
    # 项目生命周期：归档/恢复；删除进入待删除期并可恢复，到期清除（SPEC.md 第 6.3 节）。
    ProjectLifecycleStatus: {
        ProjectLifecycleStatus.ACTIVE: frozenset(
            {ProjectLifecycleStatus.ARCHIVED, ProjectLifecycleStatus.PENDING_DELETION}
        ),
        ProjectLifecycleStatus.ARCHIVED: frozenset(
            {ProjectLifecycleStatus.ACTIVE, ProjectLifecycleStatus.PENDING_DELETION}
        ),
        ProjectLifecycleStatus.PENDING_DELETION: frozenset(
            {ProjectLifecycleStatus.ACTIVE, ProjectLifecycleStatus.DELETED}
        ),
    },
    # 上传会话：PENDING 完成/过期/取消；终态不可再变（过期会话不能完成接入）。
    UploadSessionStatus: {
        UploadSessionStatus.PENDING: frozenset({
            UploadSessionStatus.COMPLETED,
            UploadSessionStatus.EXPIRED,
            UploadSessionStatus.CANCELLED,
        }),
    },
}


def is_valid_transition(
    machine: type[StrEnum], current: StrEnum, target: StrEnum
) -> bool:
    """判断转换是否合法；不抛异常。"""
    table = _TRANSITIONS.get(machine)
    if table is None:
        return False
    return target in table.get(current, frozenset())


def validate_transition(
    machine: type[StrEnum], current: StrEnum, target: StrEnum
) -> None:
    """校验转换；非法时抛出 InvalidTransitionError。

    用例与实体在改变状态前调用本函数，把非法转换暴露在边界处，而非依赖数据库
    事后报错。合法转换静默通过。
    """
    table = _TRANSITIONS.get(machine)
    if table is None:
        raise InvalidTransitionError(f"未定义状态机：{machine.__name__}")
    allowed = table.get(current, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            f"非法状态转换：{machine.__name__} {current.value} -> {target.value}"
        )
