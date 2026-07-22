"""集中状态机目录（A-021）。

SPEC.md 第 5.2～5.5、6.16 节定义了文件接入、页面、分析运行（含完整性）、
任务、风险复核与报告的生命周期状态。本模块是这些状态的唯一权威定义，
确保“所有状态具有唯一名称且无重复定义”（ADR-011）。

各状态机使用独立 StrEnum 表达，状态字符串值在各机内部唯一；转换规则由
A-022 的通用验证器集中维护，状态本身不承载转换逻辑。
"""

from __future__ import annotations

from enum import StrEnum


class DocumentVersionStatus(StrEnum):
    """文件版本接入状态（SPEC.md 第 5.2 节）。"""

    UPLOADING = "UPLOADING"
    STORED = "STORED"
    VALIDATING = "VALIDATING"
    READY = "READY"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    # 异常终态。
    REJECTED = "REJECTED"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    PROCESSING_FAILED = "PROCESSING_FAILED"


class PageStatus(StrEnum):
    """页面解析状态（SPEC.md 第 5.2 节）。"""

    PENDING = "PENDING"
    NATIVE_TEXT_READY = "NATIVE_TEXT_READY"
    OCR_REQUIRED = "OCR_REQUIRED"
    OCR_READY = "OCR_READY"
    FAILED = "FAILED"


class AnalysisRunStatus(StrEnum):
    """分析运行状态（SPEC.md 第 5.3 节）。"""

    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    EXTRACTING = "EXTRACTING"
    ANALYZING = "ANALYZING"
    VERIFYING = "VERIFYING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    READY = "READY"
    PUBLISHED = "PUBLISHED"
    # 可从活动状态进入。
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    # 新有效文件/规则或 Schema 变更后，已发布报告的运行进入过期。
    OUTDATED = "OUTDATED"


class AnalysisRunCompleteness(StrEnum):
    """分析运行完整性，独立于状态（SPEC.md 第 5.3 节、ADR-011）。"""

    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class AnalysisTaskStatus(StrEnum):
    """原子任务状态（SPEC.md 第 5.4 节）。"""

    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReviewStatus(StrEnum):
    """风险复核状态（SPEC.md 第 5.5 节）。"""

    DETECTED = "DETECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CONFIRMED = "CONFIRMED"
    MODIFIED = "MODIFIED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"


class ReportSnapshotStatus(StrEnum):
    """报告快照状态（SPEC.md 第 6.16 节）。"""

    GENERATING = "GENERATING"
    AVAILABLE = "AVAILABLE"
    FAILED = "FAILED"
    # 新有效文件进入后旧快照标记过期，内容不变。
    OUTDATED = "OUTDATED"


# 状态机注册表：机名 -> 枚举类。集中暴露，便于校验“唯一名称、无重复定义”。
STATE_MACHINES: dict[str, type[StrEnum]] = {
    "document_version": DocumentVersionStatus,
    "page": PageStatus,
    "analysis_run": AnalysisRunStatus,
    "analysis_run_completeness": AnalysisRunCompleteness,
    "analysis_task": AnalysisTaskStatus,
    "review": ReviewStatus,
    "report_snapshot": ReportSnapshotStatus,
}
