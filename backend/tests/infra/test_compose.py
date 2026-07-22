"""开发环境 Compose 配置的结构验证（A-016～A-019）。

当前运行环境未安装 Docker，无法执行 `docker compose up` 的运行时验证
（如“重启后测试数据仍存在”）。因此本测试对 Compose 文件做结构性校验：
服务、健康检查、命名数据卷与端口绑定约定是否符合 SPEC.md 第 4.2 节与
各任务交付物要求。运行时验证待 Docker 就绪后补充（见 PROGRESS.md）。
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE = REPO_ROOT / "infra" / "docker-compose.dev.yml"


def _load() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_compose_is_valid_yaml_with_services() -> None:
    cfg = _load()
    assert "services" in cfg and cfg["services"], "Compose 缺少 services"


def test_postgres_service_has_healthcheck_and_persistent_volume() -> None:
    """PostgreSQL 服务存在健康检查与命名数据卷（重启持久）。"""
    cfg = _load()
    pg = cfg["services"].get("postgres")
    assert pg is not None, "缺少 postgres 服务"
    healthcheck = pg.get("healthcheck")
    assert healthcheck and healthcheck.get("test"), "postgres 缺少健康检查"
    # 数据持久化到命名卷。
    volumes = pg.get("volumes", [])
    assert any("var/lib/postgresql/data" in v for v in volumes), "postgres 未挂载数据卷"


def test_postgres_port_bound_to_loopback_only() -> None:
    """内部端口仅绑定本地回环，不对外公开（SPEC.md 第 4.2 节）。"""
    cfg = _load()
    pg = cfg["services"]["postgres"]
    for binding in pg.get("ports", []):
        # 形如 "127.0.0.1:5432:5432"；不允许 0.0.0.0 或仅端口暴露。
        assert str(binding).startswith("127.0.0.1:"), f"端口绑定非回环：{binding}"


def test_postgres_named_volume_declared() -> None:
    cfg = _load()
    assert "postgres_data" in cfg.get("volumes", {}), "未声明 postgres_data 命名卷"


def test_redis_service_has_healthcheck_and_persistence() -> None:
    """Redis 服务存在健康检查与持久化卷（A-017）。"""
    cfg = _load()
    redis = cfg["services"].get("redis")
    assert redis is not None, "缺少 redis 服务"
    healthcheck = redis.get("healthcheck")
    assert healthcheck and healthcheck.get("test"), "redis 缺少健康检查"
    volumes = redis.get("volumes", [])
    assert any("/data" in v for v in volumes), "redis 未挂载持久化卷"
    for binding in redis.get("ports", []):
        assert str(binding).startswith("127.0.0.1:"), f"端口绑定非回环：{binding}"
