"""project 模块 ORM Model（B-001）。

projects 表：项目顶层归属边界。业务主键为系统生成的 UUID（SPEC.md 第 6.3 节
“项目名称不是唯一键，业务主键使用系统生成的 UUID”）。

刻意不含任何身份字段（organization_id/user_id/created_by/reviewed_by 等），
由 A-024 架构护栏与 B-001 验证共同保证（SPEC.md 第 4.1、15.1 节）。

列使用可移植 SQLAlchemy 类型，迁移在 SQLite（测试）与 PostgreSQL（生产）
均可运行。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from tender_insight.shared.orm import Base, TimestampMixin


class ProjectModel(Base, TimestampMixin):
    """projects 表 ORM Model。"""

    __tablename__ = "projects"

    # 系统生成的业务主键 UUID；不由用户身份推导。
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)

    # 项目名称：不是唯一键（SPEC.md 第 6.3 节）。
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 地区（四川省内）。
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    # 行业：房屋建筑工程 / 市政工程。
    industry: Mapped[str] = mapped_column(String(64), nullable=False)
    # 项目类型。
    project_type: Mapped[str] = mapped_column(String(64), nullable=False)

    # 生命周期状态：取值见 ProjectLifecycleStatus；存储字符串值。
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False)

    # 归档时间（可恢复，归档项目默认不出现在活动列表）。
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 删除请求时间：进入 30 天待删除期的起点。
    pending_deletion_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # 实际清除时间（到期后业务数据清除，保留最小审计凭证）。
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 乐观并发版本号：编辑冲突时旧版本不覆盖较新数据（SPEC.md 第 6.3、11.3 节）。
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
