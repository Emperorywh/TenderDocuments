"""example 参考样例分层的行为测试（A-005 辅助验证）。

证明四层模板可端到端协作：API 层调用应用用例，用例通过端口取得策略并交给
领域服务组装结果，基础设施层提供端口实现。该测试不涉及真实业务，仅固化
分层协作方式，供后续业务模块参照。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tender_insight.main import create_app
from tender_insight.modules.example.api import create_router
from tender_insight.modules.example.application import greet
from tender_insight.modules.example.domain.greeting import (
    GreetingText,
    InvalidGreetingTitle,
    compose_greeting,
)


def test_domain_assembles_greeting() -> None:
    """领域服务按称呼与主体组装问候。"""
    greeting = compose_greeting(title="团队", subject="招标组", message="开工")
    assert greeting.title == "团队"
    assert greeting.text.value == "团队，招标组：开工"


def test_domain_rejects_invalid_title() -> None:
    """非法称呼在领域层即被拒绝。"""
    try:
        compose_greeting(title="主人", subject="招标组", message="开工")
    except InvalidGreetingTitle:
        return
    raise AssertionError("非法称呼未被领域层拒绝")


def test_use_case_uses_policy_port() -> None:
    """应用用例通过端口取得消息，端口可被替换（依赖注入）。"""
    calls: list[str] = []

    class RecordingPolicy:
        def message_for(self, subject: str) -> str:
            calls.append(subject)
            return "已记录"

    greeting = greet(title="先生", subject="张工", policy=RecordingPolicy())
    assert calls == ["张工"]
    assert greeting.text.value == "先生，张工：已记录"


def test_api_router_returns_greeting() -> None:
    """API 层协议转换正常，调用链贯通至默认适配器。"""
    app = create_app()
    app.include_router(create_router())
    with TestClient(app) as client:
        response = client.get("/api/v1/example/greeting", params={"title": "女士", "subject": "李工"})
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "女士"
    assert body["subject"] == "李工"
    assert body["text"] == "女士，李工：工程已就绪，等待业务接入"


def test_greeting_text_trims_and_rejects_empty() -> None:
    """值对象构造即校验，空文本被拒绝。"""
    assert GreetingText("  hi  ").value == "hi"
    try:
        GreetingText("   ")
    except InvalidGreetingTitle:
        return
    raise AssertionError("空文本未被值对象拒绝")
