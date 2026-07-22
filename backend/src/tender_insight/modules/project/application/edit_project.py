"""编辑项目应用用例（B-006）。

按 SPEC.md 第 6.3、11.3 节实现乐观并发：调用方传入其读取时的版本号
expected_version，与当前版本不一致则抛 ConflictError，绝不覆盖较新数据。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tender_insight.modules.project.domain.project import Project
from tender_insight.shared.errors import ConflictError, NotFoundError
from tender_insight.shared.identifiers import Uuid


class EditProjectCommand(BaseModel):
    """编辑项目命令；project_id 为字符串形式，expected_version 为乐观版本号。"""

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
    """编辑项目用例；执行乐观版本检查并在成功时提交。"""

    def __init__(self, repository, session) -> None:
        self._repository = repository
        self._session = session

    def execute(self, command: EditProjectCommand) -> EditProjectResult:
        project_id = Uuid.from_str(command.project_id)
        project = self._repository.get(project_id)
        if project is None:
            raise NotFoundError(f"项目不存在：{command.project_id}")

        # 乐观并发：期望版本与当前不一致即冲突，不覆盖较新数据。
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
        self._session.commit()
        return _to_result(project)


def _to_result(project: Project) -> EditProjectResult:
    return EditProjectResult(
        project_id=str(project.id),
        version=project.version,
        name=project.name,
        region=project.region,
        industry=project.industry,
        project_type=project.project_type,
    )
