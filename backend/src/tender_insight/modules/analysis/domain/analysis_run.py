"""AnalysisRun 领域聚合（D-002）。

一次完整分析运行的编排聚合。封装运行状态机不变量：所有状态转换经 shared
state_transitions 集中校验，非法转换抛 InvalidTransitionError（映射 409）。
完整性（completeness）是独立字段，与状态分离建模，禁止用单字段混合
（SPEC.md 第 5.3 节、ADR-011）。

输入指纹（input_fingerprint）与输入版本集合（input_version_ids）一经创建不可变：
它们定义了本次分析“看到了什么输入”，运行期间不得变更（SPEC.md 第 11.5 节）。

设计要点：
- 纯领域模型（标准库 + shared 纯值对象/状态机），不依赖 Web/ORM/队列/SDK；
- 可变命令接收可注入 Clock，使 started_at 可测试；
- 状态与完整性各自独立，转换与完整性计算不得耦合。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from tender_insight.shared.business_time import BusinessInstant, Clock
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.state_transitions import validate_transition
from tender_insight.shared.states import AnalysisRunCompleteness, AnalysisRunStatus


@dataclass
class AnalysisRun:
    """分析运行聚合根。

    通过 create 工厂构造为 DRAFT；状态命令就地变更 status（与 completeness）。
    input_fingerprint 与 input_version_ids 创建后只读。
    """

    id: Uuid
    project_id: Uuid
    status: AnalysisRunStatus
    input_fingerprint: str
    # 有序输入版本集合（生效顺序，C-023/C-025）；创建后不可变。
    input_version_ids: tuple[Uuid, ...] = field(default_factory=tuple)
    # 完整性独立于状态；运行完成前为 None。
    completeness: AnalysisRunCompleteness | None = None
    started_at: datetime | None = None

    def __post_init__(self) -> None:
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        """输入指纹与版本集合为运行不可变不变量，必须非空。"""
        if not self.input_fingerprint.strip():
            raise ValueError("输入指纹不能为空")
        if not self.input_version_ids:
            raise ValueError("分析运行必须包含至少一个输入版本")

    # ---- 工厂 ----

    @classmethod
    def create(
        cls,
        *,
        project_id: Uuid,
        input_fingerprint: str,
        input_version_ids: tuple[Uuid, ...] | list[Uuid],
        run_id: Uuid | None = None,
    ) -> AnalysisRun:
        """创建 DRAFT 运行；输入指纹与版本集合一经绑定即不可变。"""
        return cls(
            id=run_id if run_id is not None else Uuid.new(),
            project_id=project_id,
            status=AnalysisRunStatus.DRAFT,
            input_fingerprint=input_fingerprint,
            input_version_ids=tuple(input_version_ids),
        )

    # ---- 状态转换（集中校验，非法转换抛 InvalidTransitionError）----

    def _transition(self, target: AnalysisRunStatus) -> None:
        validate_transition(AnalysisRunStatus, self.status, target)
        self.status = target

    def queue(self) -> None:
        """DRAFT → QUEUED：运行已入队待调度。"""
        self._transition(AnalysisRunStatus.QUEUED)

    def start_parsing(self, *, clock: Clock | None = None) -> None:
        """QUEUED → PARSING：开始解析，记录业务发起时刻。"""
        self._transition(AnalysisRunStatus.PARSING)
        self.started_at = BusinessInstant.now(clock=clock).value

    def start_extracting(self) -> None:
        """PARSING → EXTRACTING。"""
        self._transition(AnalysisRunStatus.EXTRACTING)

    def start_analyzing(self) -> None:
        """EXTRACTING → ANALYZING。"""
        self._transition(AnalysisRunStatus.ANALYZING)

    def start_verifying(self) -> None:
        """ANALYZING → VERIFYING。"""
        self._transition(AnalysisRunStatus.VERIFYING)

    def require_review(self) -> None:
        """VERIFYING → REVIEW_REQUIRED：存在需人工复核项。"""
        self._transition(AnalysisRunStatus.REVIEW_REQUIRED)

    def mark_ready(self, *, completeness: AnalysisRunCompleteness) -> None:
        """VERIFYING/REVIEW_REQUIRED → READY：分析完成，同时确定完整性。"""
        self._transition(AnalysisRunStatus.READY)
        # 完整性独立字段，到达 READY 时确定（COMPLETE 或 INCOMPLETE）。
        self.completeness = completeness

    def publish(self) -> None:
        """READY → PUBLISHED：报告已发布（满足发布条件后）。"""
        self._transition(AnalysisRunStatus.PUBLISHED)

    def request_cancel(self) -> None:
        """活动状态 → CANCEL_REQUESTED：请求取消（协作停止）。

        终态（CANCELLED/FAILED/PUBLISHED/OUTDATED）不可请求取消。
        """
        self._transition(AnalysisRunStatus.CANCEL_REQUESTED)

    def confirm_cancelled(self) -> None:
        """CANCEL_REQUESTED → CANCELLED：取消完成。"""
        self._transition(AnalysisRunStatus.CANCELLED)

    def mark_failed(self) -> None:
        """活动状态 → FAILED：连续失败，保留已完成产物，不进入 READY。"""
        self._transition(AnalysisRunStatus.FAILED)

    def mark_outdated(self) -> None:
        """PUBLISHED → OUTDATED：新有效文件/规则/Schema 变更后报告过期。

        历史报告内容不变，仅状态立即过期（SPEC.md 第 5.3、11.5 节）。
        """
        self._transition(AnalysisRunStatus.OUTDATED)

    # ---- 完整性（独立于状态）----

    def set_completeness(self, completeness: AnalysisRunCompleteness) -> None:
        """独立设置完整性字段；不改变状态（ADR-011）。"""
        self.completeness = completeness
