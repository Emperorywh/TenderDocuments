"""请求删除项目应用用例（B-012）。

删除只改变生命周期（进入 30 天待删除期），不立即物理清除业务数据；
pending_deletion_at 记录待删除起点，到期后由清除用例（J-009）处理
（SPEC.md 第 6.3 节）。
"""

from __future__ import annotations

from pydantic import BaseModel

from tender_insight.shared.errors import NotFoundError
from tender_insight.shared.identifiers import Uuid


class DeleteProjectCommand(BaseModel):
    project_id: str


class DeleteProjectResult(BaseModel):
    project_id: str
    lifecycle_state: str
    pending_deletion: bool


class DeleteProjectUseCase:
    def __init__(self, repository, session) -> None:
        self._repository = repository
        self._session = session

    def execute(self, command: DeleteProjectCommand) -> DeleteProjectResult:
        project_id = Uuid.from_str(command.project_id)
        project = self._repository.get(project_id)
        if project is None:
            raise NotFoundError(f"项目不存在：{command.project_id}")
        project.request_deletion()
        self._repository.save(project)
        self._session.commit()
        return DeleteProjectResult(
            project_id=str(project.id),
            lifecycle_state=project.lifecycle_state.value,
            pending_deletion=True,
        )
