"""example 模块 API 层。

只做协议转换：解析请求、组装应用用例所需上下文、调用用例并返回响应。
不承载业务规则；业务规则在 domain，编排在 application。

本参考样例提供一个 APIRouter，演示业务路由将以独立模块方式挂载到
``/api/v1`` 前缀下；为避免污染生产 API，主应用（main.py）默认不挂载本路由。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from tender_insight.modules.example.application import greet
from tender_insight.modules.example.domain.greeting import Greeting
from tender_insight.modules.example.infrastructure import DefaultGreetingPolicy


class GreetingResponse(BaseModel):
    """问候响应 DTO。"""

    title: str
    subject: str
    text: str


def _to_response(greeting: Greeting) -> GreetingResponse:
    """领域对象到响应 DTO 的单向映射，集中在 API 层。"""
    return GreetingResponse(
        title=greeting.title,
        subject=greeting.subject,
        text=greeting.text.value,
    )


def create_router() -> APIRouter:
    """构造 example 路由。

    返回 APIRouter 而非在模块导入即注册全局路由，便于按需挂载与测试。
    """
    router = APIRouter(prefix="/api/v1/example", tags=["example"])

    @router.get("/greeting", response_model=GreetingResponse)
    def get_greeting(title: str, subject: str) -> GreetingResponse:
        # API 层组装依赖（策略）并调用用例；真实模块的策略多由依赖注入容器提供。
        greeting = greet(title=title, subject=subject, policy=DefaultGreetingPolicy())
        return _to_response(greeting)

    return router
