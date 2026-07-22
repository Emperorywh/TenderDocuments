"""Alembic 迁移环境（阶段 B 起）。

从强类型配置读取连接串，并导入所有模块 ORM Model 使其注册到 Base.metadata，
据此提供 target_metadata 供 autogenerate 与一致性校验使用。

运行时迁移为显式步骤；不在应用启动请求路径隐式执行（SPEC.md 第 13.3 节）。
测试可通过 DATABASE_URL 指向 SQLite 内存库以验证迁移可运行。
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# 确保 src/ 在 sys.path 上，以便导入 tender_insight 包。
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR / "src"))

from tender_insight.shared.orm import Base  # noqa: E402

# 显式导入各模块 ORM Model，使其注册到 metadata。新增模块时在此补充 import。
from tender_insight.modules.document.infrastructure.models import UploadSessionModel  # noqa: E402,F401
from tender_insight.modules.operation_log.infrastructure.models import OperationLogModel  # noqa: E402,F401
from tender_insight.modules.project.infrastructure.models import ProjectModel  # noqa: E402,F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 连接串优先使用显式设置（测试经 cfg 注入），否则从环境变量读取（生产）。
if not config.get_main_option("sqlalchemy.url"):
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本而不连接数据库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
