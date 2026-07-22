"""project 模块 SQLAlchemy 仓储适配器（B-003）。

实现 application.ProjectRepository 端口，负责领域 Project 与 ORM ProjectModel
之间的映射。仓储不持有业务规则，仅做持久化与回读；事务边界由应用用例控制。

依赖方向：infrastructure → application/domain（单向），不被 domain 反向导入。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from tender_insight.modules.project.domain.project import Project
from tender_insight.modules.project.infrastructure.models import ProjectModel
from tender_insight.shared.identifiers import Uuid
from tender_insight.shared.states import ProjectLifecycleStatus


def _ensure_aware(value: datetime | None) -> datetime | None:
    """读取的时间戳若为 naive（SQLite 不保留时区），按 UTC 还原为 aware。

    生产 PostgreSQL 的 timestamptz 本就是 aware，此处为兼容测试库的规整；
    保证领域层始终拿到带时区时间（与 BusinessInstant 一致）。
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class SqlAlchemyProjectRepository:
    """ProjectRepository 端口的 SQLAlchemy 实现。

    不在仓储内 commit/rollback；调用方（用例）在事务边界提交或回滚，
    使“事务回滚不留数据”可由用例测试验证。
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, project: Project) -> None:
        self._session.add(_to_orm(project))

    def get(self, project_id: Uuid) -> Project | None:
        orm = self._session.get(ProjectModel, project_id.value)
        return _to_domain(orm) if orm is not None else None

    def save(self, project: Project) -> None:
        """保存变更：按 id 载入既有 ORM 并覆盖字段。

        乐观并发（版本冲突）在 B-006 强化；此处先以直接覆盖实现 save 契约。
        """
        orm = self._session.get(ProjectModel, project.id.value)
        if orm is None:
            # 未见记录则按新增处理；正常流程由 add 负责，此处兜底。
            self._session.add(_to_orm(project))
            return
        orm.name = project.name
        orm.region = project.region
        orm.industry = project.industry
        orm.project_type = project.project_type
        orm.lifecycle_state = project.lifecycle_state.value
        orm.archived_at = project.archived_at
        orm.pending_deletion_at = project.pending_deletion_at
        orm.deleted_at = project.deleted_at
        orm.version = project.version


def _to_orm(project: Project) -> ProjectModel:
    """领域 Project → ORM ProjectModel。"""
    return ProjectModel(
        id=project.id.value,
        name=project.name,
        region=project.region,
        industry=project.industry,
        project_type=project.project_type,
        lifecycle_state=project.lifecycle_state.value,
        archived_at=project.archived_at,
        pending_deletion_at=project.pending_deletion_at,
        deleted_at=project.deleted_at,
        version=project.version,
    )


def _to_domain(orm: ProjectModel) -> Project:
    """ORM ProjectModel → 领域 Project。created_at/updated_at 为基础设施审计字段，不回灌领域。"""
    return Project(
        id=Uuid(orm.id),
        name=orm.name,
        region=orm.region,
        industry=orm.industry,
        project_type=orm.project_type,
        lifecycle_state=ProjectLifecycleStatus(orm.lifecycle_state),
        version=orm.version,
        archived_at=_ensure_aware(orm.archived_at),
        pending_deletion_at=_ensure_aware(orm.pending_deletion_at),
        deleted_at=_ensure_aware(orm.deleted_at),
    )
