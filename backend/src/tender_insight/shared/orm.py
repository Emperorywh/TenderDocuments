"""SQLAlchemy ORM 公共基类与混入（阶段 B 起）。

提供所有模块 ORM Model 共用的声明基类、命名约定与时间戳混入。Base 使用
SQLAlchemy 2.0 声明式映射；为便于在各模块 infrastructure 层定义 Model，
统一约束命名（索引、外键、唯一约束），避免散落不一致命名。

类型选择遵循可移植原则：UUID 用 sa.Uuid（PG 原生 uuid、SQLite 回退为
CHAR(32)），金额/分值用 Numeric，时间用 DateTime(timezone=True)，使迁移在
SQLite（本机测试）与 PostgreSQL（生产目标）均可运行。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 统一命名约定，使 Alembic 自动生成的约束名稳定可审计。
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """所有 ORM Model 的声明基类。

    metadata 绑定命名约定；各模块在 infrastructure 层定义 Model 并注册到本
    metadata，Alembic env.py 据此生成迁移。
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """创建/更新时间戳混入。

    created_at 由数据库 now() 默认填充；updated_at 由数据库在每次更新时刷新
    （onupdate）。两者均为带时区时间。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
