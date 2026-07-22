"""强类型配置（A-013）。

SPEC.md 第 13.2 节要求启动时执行配置 Schema 校验，缺少关键配置必须失败退出；
第 17 章要求部署参数通过强类型配置进入系统，不得散落为魔法常量。

关键基础设施连接（数据库、Redis、对象存储、DeepSeek）声明为必填字段：
缺少即在校验阶段抛 ValidationError，使进程“明确失败退出”，而非带着空配置
静默运行。文件限额等非阻塞参数提供默认值，但仍是强类型字段，避免散落常量。

环境变量名与字段名一致（大小写不敏感），如 database_url 读取 DATABASE_URL，
deepseek_base_url 读取 DEEPSEEK_BASE_URL，与 PLAN.md 第 8.1 节命名一致。
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """进程级强类型配置。

    必填字段缺失时，pydantic-settings 在构造阶段即抛出 ValidationError，
    调用方据此拒绝启动；密钥使用 SecretStr，避免在日志或序列化中泄漏明文。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- 数据库（PostgreSQL，业务状态唯一事实来源）----
    database_url: str

    # ---- Redis（队列与缓存，不承载权威业务状态）----
    redis_url: str

    # ---- 对象存储（S3 兼容 / MinIO，对象默认私有）----
    s3_endpoint_url: str
    s3_access_key: SecretStr
    s3_secret_key: SecretStr
    s3_bucket: str
    s3_region: str = "us-east-1"

    # ---- DeepSeek（外部模型，OpenAI 兼容）----
    deepseek_base_url: str
    deepseek_api_key: SecretStr
    deepseek_fast_model: str
    deepseek_strong_model: str
    deepseek_timeout_seconds: float = 60.0
    deepseek_max_concurrency: int = 4
    deepseek_project_budget: Decimal = Decimal("100")
    deepseek_json_mode: bool = True

    # ---- 文件与项目限额（SPEC.md 第 3.2、17 章）----
    # 单文件最大字节数（部署可配置）。
    max_file_bytes: int = 100 * 1024 * 1024
    # 单项目最大文件数（部署可配置）。
    max_files_per_project: int = 100
    # 单项目最大总字节数（部署可配置）。
    max_project_bytes: int = 1024 * 1024 * 1024
    # 单项目最大页数：业务验收硬限制（SPEC.md 第 3.2 节）。
    max_project_pages: int = 500

    # ---- 对象授权 URL 有效期（秒）----
    presigned_url_ttl_seconds: int = 900

    # ---- 运行开关（发布前停止接单，见 K-014）----
    accept_new_analysis: bool = True

    # ---- 日志 ----
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回缓存的配置单例。

    首次调用即触发配置校验；关键配置缺失时抛 ValidationError，调用方（进程
    启动入口）应让其向上传播以“明确失败退出”，不在此处吞掉异常。

    必填字段由 pydantic-settings 从环境变量注入，构造无需显式传参；静态类型
    检查无法感知这一运行时来源，故在此处定向豁免 reportCallIssue。
    """
    return Settings()  # pyright: ignore[reportCallIssue]
