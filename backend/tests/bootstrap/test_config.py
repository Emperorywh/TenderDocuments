"""强类型配置测试（A-013 独立验证）。

验证缺少关键配置时进程明确失败退出，完整配置可正常构造且密钥不泄漏。
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from tender_insight.bootstrap.config import Settings

# 关键（必填）配置键。
REQUIRED_KEYS: dict[str, str] = {
    "database_url": "postgresql+psycopg://u:p@h:5432/d",
    "redis_url": "redis://h:6379/0",
    "s3_endpoint_url": "http://h:9000",
    "s3_access_key": "ak",
    "s3_secret_key": "sk",
    "s3_bucket": "tender",
    "deepseek_base_url": "https://api.deepseek.com",
    "deepseek_api_key": "dk",
    "deepseek_fast_model": "fast",
    "deepseek_strong_model": "strong",
}


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """清除所有可能的配置环境变量，确保测试基线干净。"""
    for key in list(REQUIRED_KEYS) + [
        "s3_region",
        "deepseek_timeout_seconds",
        "deepseek_max_concurrency",
        "deepseek_project_budget",
        "max_file_bytes",
        "max_files_per_project",
        "max_project_bytes",
        "max_project_pages",
        "presigned_url_ttl_seconds",
        "accept_new_analysis",
        "log_level",
    ]:
        monkeypatch.delenv(key, raising=False)


def _set_all(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_env(monkeypatch)
    for key, value in REQUIRED_KEYS.items():
        monkeypatch.setenv(key, value)


def test_missing_critical_config_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺少关键配置时构造失败（进程明确失败退出）。"""
    _clear_env(monkeypatch)
    # 仅设置除 database_url 外的全部关键配置。
    for key, value in REQUIRED_KEYS.items():
        if key == "database_url":
            continue
        monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError) as info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    # 失败信息指向缺失字段，便于排查。
    assert "database_url" in str(info.value)


def test_full_config_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    """完整关键配置可正常构造。"""
    _set_all(monkeypatch)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.database_url.startswith("postgresql")
    assert settings.max_project_pages == 500


def test_defaults_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    """非必填配置使用默认值（无魔法常量散落）。"""
    _set_all(monkeypatch)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.max_project_pages == 500
    assert settings.deepseek_max_concurrency == 4
    assert settings.presigned_url_ttl_seconds == 900
    assert settings.accept_new_analysis is True
    assert settings.deepseek_project_budget == Decimal("100")


def test_secrets_are_not_plain_strings(monkeypatch: pytest.MonkeyPatch) -> None:
    """密钥以 SecretStr 承载，str() 不泄漏明文。"""
    _set_all(monkeypatch)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert "dk" not in str(settings.deepseek_api_key)
    assert "sk" not in str(settings.s3_secret_key)


def test_overridable_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """限额可经环境变量覆盖，领域代码无需改动。"""
    _set_all(monkeypatch)
    monkeypatch.setenv("MAX_PROJECT_PAGES", "400")
    monkeypatch.setenv("ACCEPT_NEW_ANALYSIS", "false")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.max_project_pages == 400
    assert settings.accept_new_analysis is False
