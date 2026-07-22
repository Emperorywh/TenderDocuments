"""数据库会话与引擎装配（阶段 B 起）。

从强类型配置（A-013）读取连接串，构造 SQLAlchemy 引擎与会话工厂。会话以
依赖注入方式提供给应用用例（每个用例一个短事务），不在领域层持有会话。

本模块刻意不在导入期创建全局引擎，避免测试与多配置场景被隐式状态绑架；
由 FastAPI 依赖（阶段 B 应用层）或 Worker 按需调用 create_session_factory。
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from tender_insight.bootstrap.config import Settings

# 进程级会话工厂占位；启动时由 configure_session_factory 注入，测试通过依赖
# 覆盖（dependency_overrides）替换，避免全局状态污染测试。
_session_factory: sessionmaker[Session] | None = None


def create_engine_from_settings(settings: Settings) -> Engine:
    """依据配置创建 SQLAlchemy 引擎。

    预留 future=True 以使用 SQLAlchemy 2.0 风格；具体连接池参数由配置决定。
    """
    return create_engine(settings.database_url, future=True, pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """创建会话工厂；调用方负责在用例事务边界内 open/close。"""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def configure_session_factory(factory: sessionmaker[Session]) -> None:
    """启动期注入会话工厂，供 get_session 依赖使用。"""
    global _session_factory
    _session_factory = factory


def get_session() -> Iterator[Session]:
    """FastAPI 依赖：按请求提供会话并在结束时关闭。

    工厂未配置时抛 RuntimeError（启动装配错误），不静默回退。
    """
    if _session_factory is None:
        raise RuntimeError("数据库会话工厂未配置，请先调用 configure_session_factory")
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()

