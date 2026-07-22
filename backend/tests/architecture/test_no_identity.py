"""首版无身份模块架构约束验证（A-024）。

SPEC.md 第 3.3、4.1 节与第 15.1 节要求：首版不建立用户、组织、成员、角色、
会话、Token、RBAC、租户或 RLS 相关业务模块；业务表不含 organization_id、
user_id、created_by、reviewed_by、tenant_id 等身份字段。本测试是长期护栏，
确保后续任务不会无意引入身份边界（ADR-014）。

注意：contextvars.Token 等标准库类型不计入“身份 Token”，本测试只针对业务
模块名与身份字段标识符。
"""

from __future__ import annotations

import re
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"

# 禁止的业务模块/包目录名（身份相关）。
FORBIDDEN_MODULE_DIRS: frozenset[str] = frozenset(
    {
        "identity",
        "auth",
        "rbac",
        "user",
        "users",
        "tenant",
        "tenants",
        "membership",
        "memberships",
        "role",
        "roles",
        "session",
        "sessions",
        "account",
        "accounts",
    }
)

# 禁止的身份字段标识符（数据库列/模型字段）。
IDENTITY_FIELD_PATTERN = re.compile(r"\b(organization_id|user_id|tenant_id|created_by|reviewed_by)\b")


def test_no_identity_business_modules() -> None:
    """modules/ 下不存在身份相关业务模块目录。"""
    modules_root = SRC_ROOT / "tender_insight" / "modules"
    if not modules_root.exists():
        return
    found = [p.name for p in modules_root.iterdir() if p.is_dir() and p.name in FORBIDDEN_MODULE_DIRS]
    assert not found, f"存在被禁的身份业务模块：{found}"


def test_no_identity_fields_in_source() -> None:
    """源码中不出现 organization_id/user_id/created_by 等身份字段。"""
    offenders: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in IDENTITY_FIELD_PATTERN.finditer(text):
            offenders.append(f"{path.relative_to(SRC_ROOT)}: {match.group(1)}")
    assert not offenders, "源码出现身份字段：\n" + "\n".join(offenders)


def test_no_identity_entity_class_definitions() -> None:
    """不定义 User/Organization/Tenant/Membership/Role/Session 等身份实体类。

    扫描 class 定义名；contextvars.Token 等类型用法不属于 class 定义，不会被误判。
    """
    forbidden_classes = {
        "User",
        "Organization",
        "Tenant",
        "Membership",
        "Role",
        "Session",
        "Account",
    }
    pattern = re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\b", re.MULTILINE)
    offenders: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            if match.group(1) in forbidden_classes:
                offenders.append(f"{path.relative_to(SRC_ROOT)}: class {match.group(1)}")
    assert not offenders, "定义了身份实体类：\n" + "\n".join(offenders)
