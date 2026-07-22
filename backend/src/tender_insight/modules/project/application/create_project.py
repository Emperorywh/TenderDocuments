"""创建项目应用用例（B-004，B-017 接入操作记录）。

编排：以 Pydantic 命令在边界做必填校验，再交由领域工厂创建 Project，经仓储
持久化并在用例事务边界提交。每个命令恰好产生一条操作记录（成功同事务、
失败独立事务），未注入录制器时跳过记录。

用例不包含业务规则本身（规则在 domain），只负责事务与协作。
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, Field

from tender_insight.modules.operation_log.application import OperationRecorder
from tender_insight.modules.operation_log.application.recording import record_command_outcome
from tender_insight.modules.project.domain.project import Project
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.request_context import current_request_context


class CreateProjectCommand(BaseModel):
    """创建项目命令；必填字段缺失时 Pydantic 校验失败。"""

    name: str = Field(min_length=1)
    region: str = Field(min_length=1)
    industry: str = Field(min_length=1)
    project_type: str = Field(min_length=1)


class CreateProjectResult(BaseModel):
    """创建结果：返回新项目的标识与基础信息，避免直接外泄领域对象。"""

    project_id: str
    name: str
    region: str
    industry: str
    project_type: str


class CreateProjectUseCase:
    """创建项目用例。"""

    def __init__(
        self,
        repository,
        session,
        session_factory: Callable[[], object] | None = None,
        open_recorder: Callable[[object], OperationRecorder] | None = None,
    ) -> None:
        self._repository = repository
        self._session = session
        self._session_factory = session_factory
        self._open_recorder = open_recorder

    def execute(self, command: CreateProjectCommand) -> CreateProjectResult:
        # 预先生成项目 ID，使操作记录的 resource_id 在执行前可知。
        project_id = Uuid.new()
        ctx = current_request_context()

        def perform() -> CreateProjectResult:
            # 领域工厂构造活动项目；空字段在此被领域不变量拒绝。
            project = Project.create(
                project_id=project_id,
                name=command.name,
                region=command.region,
                industry=command.industry,
                project_type=command.project_type,
            )
            self._repository.add(project)
            return _to_result(project)

        return record_command_outcome(
            session=self._session,
            session_factory=self._session_factory,  # type: ignore[arg-type]
            open_recorder=self._open_recorder,  # type: ignore[arg-type]
            action="project.create",
            resource_type="project",
            resource_id=str(project_id),
            request_id=ctx.request_id if ctx is not None else None,
            perform=perform,
        )


def _to_result(project: Project) -> CreateProjectResult:
    return CreateProjectResult(
        project_id=str(project.id),
        name=project.name,
        region=project.region,
        industry=project.industry,
        project_type=project.project_type,
    )
