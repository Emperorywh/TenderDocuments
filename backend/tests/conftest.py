"""pytest 共享夹具。

提供基于临时文件 SQLite 的数据库夹具：先以 Alembic 迁移建表，再提供引擎与
会话工厂。本机无 PostgreSQL/Docker 时，用 SQLite 作为可运行的测试库（迁移
使用可移植类型，生产仍以 PostgreSQL 为目标）。各模块仓储/集成测试复用本夹具。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# 测试环境默认配置：使 get_settings() 可在无 .env 的测试进程中成功构造。
# 这些是测试占位值，不接触任何真实服务。
_DEFAULT_TEST_ENV = {
    "DATABASE_URL": "sqlite:///test.db",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "S3_ACCESS_KEY": "test-access-key",
    "S3_SECRET_KEY": "test-secret-key",
    "S3_BUCKET": "tender",
    "DEEPSEEK_BASE_URL": "http://localhost",
    "DEEPSEEK_API_KEY": "test-deepseek-key",
    "DEEPSEEK_FAST_MODEL": "fast-model-id",
    "DEEPSEEK_STRONG_MODEL": "strong-model-id",
}
for _key, _value in _DEFAULT_TEST_ENV.items():
    os.environ.setdefault(_key, _value)

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _apply_migrations(db_url: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")


@pytest.fixture()
def sqlite_db_url(tmp_path: Path) -> str:
    """临时文件 SQLite 连接串。"""
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture()
def engine(sqlite_db_url: str) -> Engine:
    """应用迁移后的 SQLite 引擎。"""
    _apply_migrations(sqlite_db_url)
    eng = create_engine(sqlite_db_url, future=True)

    # 启用 SQLite 外键约束，使测试与生产 PostgreSQL 的 FK 行为一致。
    from sqlalchemy import event

    @event.listens_for(eng, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture()
def db_session(session_factory: sessionmaker[Session]) -> Session:
    """短事务会话；用例在边界内 commit/rollback。"""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
