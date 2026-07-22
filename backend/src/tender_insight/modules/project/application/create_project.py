"""创建项目应用用例（B-004）。

编排：以 Pydantic 命令在边界做必填校验，再交由领域工厂创建 Project，经仓储
持久化并在用例事务边界提交。领域层的非空不变量作为第二道防线。

用例不包含业务规则本身（规则在 domain），只负责事务与协作。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from tender_insight.modules.project.domain.project import Project


class CreateProjectCommand(BaseModel):
    """创建项目命令；必填字段缺失时 Pydantic 校验失败。"""

    name: str = Field(min_length=1)
    region: str = Field(min_length=1)
    industry: str = Field(min_length=1)
    project_type: str = Field(min_length=1)


class CreateProjectResult(BaseModel):
    """创建结果：返回新项目的标识与基础信息，避免直接外泄领域对象。"""

    # project_id 以标准 UUID 字符串形式对外，避免暴露内部值对象类型。
    project_id: str
    name: str
    region: str
    industry: str
    project_type: str


class CreateProjectUseCase:
    """创建项目用例。

    依赖 ProjectRepository 端口与 Session；execute 在成功时提交事务，领域异常
    向上传播（不提交），保证失败不留残留数据。
    """

    def __init__(self, repository, session) -> None:  # 类型见端口；避免循环导入用协议推断
        self._repository = repository
        self._session = session

    def execute(self, command: CreateProjectCommand) -> CreateProjectResult:
        # 领域工厂构造活动项目；空字段在此被领域不变量拒绝。
        project = Project.create(
            name=command.name,
            region=command.region,
            industry=command.industry,
            project_type=command.project_type,
        )
        self._repository.add(project)
        self._session.commit()
        return _to_result(project)


def _to_result(project: Project) -> CreateProjectResult:
    return CreateProjectResult(
        project_id=str(project.id),
        name=project.name,
        region=project.region,
        industry=project.industry,
        project_type=project.project_type,
    )
