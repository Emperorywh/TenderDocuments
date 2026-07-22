"""FastAPI 应用入口与健康检查。

本模块提供应用工厂 ``create_app`` 与模块级 ASGI 对象 ``app``，供
``uvicorn tender_insight.main:app`` 启动。首版为单实例、单工作区、无应用
鉴权模式（SPEC.md 第 4 节），因此入口不引入任何登录、会话或鉴权中间件。

按 SPEC.md 第 6.1 节，API 健康检查必须与业务接口区分：业务接口统一挂在
``/api/v1`` 前缀下，健康检查挂在独立的 ``/health``，二者不混用。
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from tender_insight import __version__


class HealthResponse(BaseModel):
    """健康检查固定契约。

    字段集合与取值在后端单方面稳定，前端与运维据此判断进程存活；
    不得在响应中夹带数据库连接、对象存储凭证或内部对象键等敏感信息。
    """

    # 存活状态固定为 "ok"；进程不可用时由 HTTP 层直接不响应或返回 5xx。
    status: Literal["ok"]
    # 服务标识固定为 tender-insight-api，便于多组件部署中区分健康来源。
    service: Literal["tender-insight-api"]
    # 应用版本，来自 tender_insight.__version__，便于核对部署镜像。
    version: str


def create_app() -> FastAPI:
    """构造 FastAPI 应用实例。

    工厂方式便于在测试中按需创建应用，并避免模块导入即绑定全局状态的隐式行为。
    当前仅注册健康检查路由；业务路由将在后续任务中以独立模块方式挂载到
    ``/api/v1`` 前缀下。
    """
    app = FastAPI(
        title="Tender Insight API",
        description="四川建筑施工招标文件智能解读与投标风险提示系统 API",
        version=__version__,
    )

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    def health() -> HealthResponse:
        """返回固定的健康检查契约。

        本端点不依赖数据库、对象存储或外部模型，保证在基础设施尚未就绪时
        也能用于存活探测；业务可用性由 ``/api/v1`` 下的各接口分别体现。
        """
        return HealthResponse(status="ok", service="tender-insight-api", version=__version__)

    return app


# 模块级 ASGI 对象，供 uvicorn 等服务器直接引用：
#   uvicorn tender_insight.main:app --host 0.0.0.0 --port 8000
app = create_app()
