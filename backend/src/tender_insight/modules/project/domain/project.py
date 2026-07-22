"""Project 聚合（B-002）。

项目是业务数据的顶层归属边界（SPEC.md 第 4.3 节）。本聚合封装项目生命周期
不变量：字段非空校验与状态转换校验都在领域层完成，使非法数据与非法转换
无法被创建。

设计要点：
- 纯领域模型（标准库 + shared 纯值对象/状态机），不依赖 Web/ORM/队列/SDK；
- 生命周期转换经 shared.state_transitions.validate_transition 校验，非法转换
  抛 InvalidTransitionError；
- 可变命令接收可注入 Clock，使时间戳可测试；
- version 在可变命令中自增，支撑乐观并发（SPEC.md 第 6.3、11.3 节）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from tender_insight.modules.project.domain.exceptions import InvalidProjectDataError
from tender_insight.shared.business_time import BusinessInstant, Clock
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.state_transitions import validate_transition
from tender_insight.shared.states import ProjectLifecycleStatus


@dataclass
class Project:
    """项目聚合根。

    通过 create 工厂构造；生命周期命令（归档、恢复、删除、清除）就地变更状态
    与时间戳并自增 version。领域不变量在构造与每次变更时校验。
    """

    id: Uuid
    name: str
    region: str
    industry: str
    project_type: str
    lifecycle_state: ProjectLifecycleStatus
    version: int = 1
    archived_at: datetime | None = None
    pending_deletion_at: datetime | None = None
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        self._validate_fields()

    def _validate_fields(self) -> None:
        """校验字段非空；首版以非空为最小不变量。"""
        if not self.name.strip():
            raise InvalidProjectDataError("项目名称不能为空")
        if not self.region.strip():
            raise InvalidProjectDataError("项目地区不能为空")
        if not self.industry.strip():
            raise InvalidProjectDataError("项目行业不能为空")
        if not self.project_type.strip():
            raise InvalidProjectDataError("项目类型不能为空")

    # ---- 工厂 ----

    @classmethod
    def create(
        cls,
        *,
        name: str,
        region: str,
        industry: str,
        project_type: str,
        project_id: Uuid | None = None,
    ) -> Project:
        """创建活动项目；未提供 id 时生成新 UUID。"""
        return cls(
            id=project_id if project_id is not None else Uuid.new(),
            name=name,
            region=region,
            industry=industry,
            project_type=project_type,
            lifecycle_state=ProjectLifecycleStatus.ACTIVE,
        )

    # ---- 生命周期命令 ----

    def _transition(self, target: ProjectLifecycleStatus, clock: Clock | None) -> None:
        """校验并执行状态转换；非法转换抛 InvalidTransitionError。"""
        # 转换表按 ProjectLifecycleStatus 查询；非法转换由验证器拒绝。
        validate_transition(ProjectLifecycleStatus, self.lifecycle_state, target)
        self.lifecycle_state = target
        self.version += 1

    def archive(self, *, clock: Clock | None = None) -> None:
        """归档（可恢复）；记录归档时间。"""
        self._transition(ProjectLifecycleStatus.ARCHIVED, clock)
        self.archived_at = BusinessInstant.now(clock=clock).value

    def restore_from_archive(self) -> None:
        """从归档恢复为活动项目。"""
        self._transition(ProjectLifecycleStatus.ACTIVE, None)

    def request_deletion(self, *, clock: Clock | None = None) -> None:
        """请求删除，进入 30 天待删除期；记录起点时间。"""
        self._transition(ProjectLifecycleStatus.PENDING_DELETION, clock)
        self.pending_deletion_at = BusinessInstant.now(clock=clock).value

    def recover_from_deletion(self) -> None:
        """待删除期内恢复为活动项目。"""
        self._transition(ProjectLifecycleStatus.ACTIVE, None)
        self.pending_deletion_at = None

    def purge(self, *, clock: Clock | None = None) -> None:
        """到期清除：业务数据清除，记录清除时间（保留最小审计凭证）。"""
        self._transition(ProjectLifecycleStatus.DELETED, clock)
        self.deleted_at = BusinessInstant.now(clock=clock).value

    # ---- 编辑命令 ----

    def update_details(
        self,
        *,
        name: str | None = None,
        region: str | None = None,
        industry: str | None = None,
        project_type: str | None = None,
    ) -> None:
        """编辑项目基础字段；仅非空字段覆盖，version 自增。"""
        # 先暂存新值，校验通过后再赋值，避免部分更新留下非法中间态。
        new_name = name if name is not None else self.name
        new_region = region if region is not None else self.region
        new_industry = industry if industry is not None else self.industry
        new_type = project_type if project_type is not None else self.project_type
        # 复用校验：构造临时对象触发 _validate_fields。
        Project(
            id=self.id,
            name=new_name,
            region=new_region,
            industry=new_industry,
            project_type=new_type,
            lifecycle_state=self.lifecycle_state,
        )
        self.name = new_name
        self.region = new_region
        self.industry = new_industry
        self.project_type = new_type
        self.version += 1
