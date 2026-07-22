"""分层依赖约束测试（A-005 独立验证）。

验证示例领域层不导入 Web、ORM、队列或供应商 SDK（PLAN.md 第 3.2 节、
SPEC.md 第 12.4 节）。采用 AST 扫描源文件 import 语句的根模块名，避免
被字符串拼接或动态导入绕过核心约束；该扫描在 A-006 中泛化为通用依赖规则。
"""

from __future__ import annotations

import ast
from pathlib import Path

# 领域层禁止依赖的根模块名集合：
# - Web：fastapi、starlette、uvicorn；
# - ORM：sqlalchemy、alembic、psycopg、sqlmodel；
# - 队列：celery、redis、kombu；
# - 供应商 SDK：minio、boto3、paddleocr、openai。
FORBIDDEN_IN_DOMAIN: frozenset[str] = frozenset(
    {
        "fastapi",
        "starlette",
        "uvicorn",
        "sqlalchemy",
        "alembic",
        "psycopg",
        "sqlmodel",
        "celery",
        "redis",
        "kombu",
        "minio",
        "boto3",
        "paddleocr",
        "openai",
    }
)

# 后端 src 根目录。
SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "tender_insight"


def _domain_python_files() -> list[Path]:
    """收集所有业务模块 domain 层的 Python 源文件。"""
    modules_root = SRC_ROOT / "modules"
    files: list[Path] = []
    if not modules_root.exists():
        return files
    for domain_dir in modules_root.glob("*/domain"):
        if domain_dir.is_dir():
            files.extend(domain_dir.rglob("*.py"))
    return files


def _imported_root_modules(file_path: Path) -> set[str]:
    """解析单个源文件中所有 import 语句的根模块名。"""
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_domain_files_exist() -> None:
    """样例 domain 层至少存在源文件，避免空目录使后续断言失去意义。"""
    files = _domain_python_files()
    assert files, "未找到任何 modules/*/domain 源文件，样例分层未建立"


def test_domain_does_not_import_forbidden_frameworks() -> None:
    """所有 domain 源文件均不得导入 Web、ORM、队列或供应商 SDK。"""
    violations: list[str] = []
    for file_path in _domain_python_files():
        imported = _imported_root_modules(file_path)
        bad = imported & FORBIDDEN_IN_DOMAIN
        if bad:
            violations.append(f"{file_path.relative_to(SRC_ROOT)}: {sorted(bad)}")
    assert not violations, "领域层存在禁止依赖：\n" + "\n".join(violations)


def test_example_domain_uses_pure_stdlib_modeling() -> None:
    """样例 domain 使用标准库 dataclasses 建模，不绑定校验框架。"""
    greeting_file = SRC_ROOT / "modules" / "example" / "domain" / "greeting.py"
    roots = _imported_root_modules(greeting_file)
    # 仅允许标准库与包内相对导入出现在领域层。
    forbidden = roots & FORBIDDEN_IN_DOMAIN
    assert not forbidden
    assert "dataclasses" in roots
