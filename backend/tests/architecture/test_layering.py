"""分层依赖约束测试（A-005 / A-006 共用）。

具体规则实现集中在 tests/architecture/dependency_rules.py（唯一权威）。
本文件只负责把规则应用到真实源码并断言无违例。
"""

from __future__ import annotations

from pathlib import Path

from tests.architecture.dependency_rules import (
    find_forbidden_domain_imports,
    find_layer_violations,
)

# backend/src 目录，即包含 tender_insight/ 的源码根。
SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


def test_no_internal_layer_reverse_dependencies() -> None:
    """真实源码不存在低层反向依赖高层的导入。"""
    violations = find_layer_violations(SRC_ROOT)
    assert not violations, "\n".join(
        f"{v.file.name}: {v.reason}（导入 {v.imported_module}）" for v in violations
    )


def test_domain_does_not_import_forbidden_frameworks() -> None:
    """真实 domain 层不导入 Web、ORM、队列或供应商 SDK。"""
    violations = find_forbidden_domain_imports(SRC_ROOT)
    assert not violations, "\n".join(
        f"{v.file.name}: {v.reason}" for v in violations
    )
