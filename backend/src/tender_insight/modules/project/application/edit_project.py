"""编辑项目应用用例（B-006，B-017 接入操作记录）。

按 SPEC.md 第 6.3、11.3 节实现乐观并发：调用方传入其读取时的版本号
expected_version，与当前版本不一致则抛 ConflictError，绝不覆盖较新数据。
每个命令恰好产生一条操作记录（未注入录制器时跳过）。
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, Field

from tender_insight.modules.operation_log.application import OperationRecorder
from tender_insight.modules.operation_log.application.recording import record_command_outcome
from tender_insight.modules.project.domain.project import Project
from tender_insight.shared.errors import ConflictError, NotFoundError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.request_context import current_request_context


class EditProjectCommand(BaseModel):
    project_id: str
    expected_version: int = Field(ge=1)
    name: str | None = None
    region: str | None = None
    industry: str | None = None
    project_type: str | None = None


class EditProjectResult(BaseModel):
    project_id: str
    version: int
    name: str
    region: str
    industry: str
    project_type: str


class EditProjectUseCase:
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

    def execute(self, command: EditProjectCommand) -> EditProjectResult:
        ctx = current_request_context()

        def perform() -> EditProjectResult:
            project_id = Uuid.from_str(command.project_id)
            project = self._repository.get(project_id)
            if project is None:
                raise NotFoundError(f"项目不存在：{command.project_id}")
            if project.version != command.expected_version:
                raise ConflictError(
                    f"项目版本冲突：期望 {command.expected_version}，当前 {project.version}"
                )
            project.update_details(
                name=command.name,
                region=command.region,
                industry=command.industry,
                project_type=command.project_type,
            )
            self._repository.save(project)
            return _to_result(project)

        return record_command_outcome(
            session=self._session,
            session_factory=self._session_factory,  # type: ignore[arg-type]
            open_recorder=self._open_recorder,  # type: ignore[arg-type]
            action="project.edit",
            resource_type="project",
            resource_id=command.project_id,
            request_id=ctx.request_id if ctx is not None else None,
            perform=perform,
        )


def _to_result(project: Project) -> EditProjectResult:
    return EditProjectResult(
        project_id=str(project.id),
        version=project.version,
        name=project.name,
        region=project.region,
        industry=project.industry,
        project_type=project.project_type,
    )
