"""Project 数据迁移测试（B-001 独立验证）。

验证空库执行迁移可创建 projects 表，且不含用户、组织或租户字段。

本机无 PostgreSQL/Docker，故使用临时文件 SQLite 作为“空库”运行 Alembic 迁移：
迁移脚本使用可移植 SQLAlchemy 类型，在 SQLite 与 PostgreSQL 均可运行；
生产目标仍为 PostgreSQL（SPEC.md 第 2.4 节）。
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _run_upgrade(db_url: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")


def test_migration_creates_projects_table(tmp_path: Path) -> None:
    """空库迁移成功，创建 projects 表。"""
    db_file = tmp_path / "empty.db"
    db_url = f"sqlite:///{db_file}"
    _run_upgrade(db_url)

    engine = create_engine(db_url)
    inspector = inspect(engine)
    assert "projects" in inspector.get_table_names()


def test_projects_table_has_required_columns(tmp_path: Path) -> None:
    """projects 表含核心字段与乐观版本号。"""
    db_url = f"sqlite:///{tmp_path / 'cols.db'}"
    _run_upgrade(db_url)
    engine = create_engine(db_url)
    cols = {c["name"] for c in inspect(engine).get_columns("projects")}

    required = {
        "id",
        "name",
        "region",
        "industry",
        "project_type",
        "lifecycle_state",
        "archived_at",
        "pending_deletion_at",
        "deleted_at",
        "version",
        "created_at",
        "updated_at",
    }
    assert required <= cols, f"缺失列：{required - cols}"


def test_projects_table_has_no_identity_fields(tmp_path: Path) -> None:
    """projects 表不含 organization_id/user_id/created_by/reviewed_by/tenant_id。"""
    db_url = f"sqlite:///{tmp_path / 'noid.db'}"
    _run_upgrade(db_url)
    engine = create_engine(db_url)
    cols = {c["name"] for c in inspect(engine).get_columns("projects")}

    forbidden = {"organization_id", "user_id", "created_by", "reviewed_by", "tenant_id"}
    assert not (cols & forbidden), f"出现身份字段：{cols & forbidden}"


def test_migration_is_reversible(tmp_path: Path) -> None:
    """迁移可回滚（downgrade 移除 projects 表）。"""
    db_url = f"sqlite:///{tmp_path / 'rev.db'}"
    _run_upgrade(db_url)

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.downgrade(cfg, "base")

    engine = create_engine(db_url)
    assert "projects" not in inspect(engine).get_table_names()
