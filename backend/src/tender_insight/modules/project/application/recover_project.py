"""恢复待删除项目应用用例（B-013）。

到期前可恢复：PENDING_DELETION → ACTIVE，并清除 pending_deletion_at。
超过保留期（30 天）则拒绝恢复（前置条件不满足），由清除用例处理（J-009）。
"""

from __future__ import annotations

from pydantic import BaseModel

from tender_insight.modules.project.domain.project import pending_deletion_deadline
from tender_insight.shared.business_time import BusinessInstant, Clock
from tender_insight.shared.errors import NotFoundError, PreconditionFailedError
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.states import ProjectLifecycleStatus


class RecoverProjectCommand(BaseModel):
    project_id: str


class RecoverProjectResult(BaseModel):
    project_id: str
    lifecycle_state: str


class RecoverProjectUseCase:
    def __init__(self, repository, session) -> None:
        self._repository = repository
        self._session = session

    def execute(
        self,
        command: RecoverProjectCommand,
        *,
        clock: Clock | None = None,
    ) -> RecoverProjectResult:
        project_id = Uuid.from_str(command.project_id)
        project = self._repository.get(project_id)
        if project is None:
            raise NotFoundError(f"项目不存在：{command.project_id}")
        if project.lifecycle_state != ProjectLifecycleStatus.PENDING_DELETION:
            # 非待删除状态不能“恢复删除”；由状态机拒绝。
            project.recover_from_deletion()  # 触发非法转换异常
            # 不应到达此处。
            raise PreconditionFailedError("项目不在待删除状态")

        # 到期边界：超过保留期则不可恢复。
        assert project.pending_deletion_at is not None
        now = BusinessInstant.now(clock=clock).value
        if now >= pending_deletion_deadline(project.pending_deletion_at):
            raise PreconditionFailedError("项目已过待删除保留期，不可恢复")

        project.recover_from_deletion()
        self._repository.save(project)
        self._session.commit()
        return RecoverProjectResult(
            project_id=str(project.id),
            lifecycle_state=project.lifecycle_state.value,
        )
