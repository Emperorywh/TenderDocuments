"""自动依赖规则验证（A-006 独立验证）。

验证规则引擎在“注入一条反向依赖后检查失败、移除后通过”。使用临时源码根
构造受控样例，不污染真实仓库；同时验证规则对真实源码当前无违例。
"""

from __future__ import annotations

from pathlib import Path

from tests.architecture.dependency_rules import (
    ModuleLayer,
    find_layer_violations,
)


def _make_module_root(tmp: Path) -> Path:
    """在临时目录下建立 tender_insight/modules 四层骨架目录。"""
    base = tmp / "tender_insight" / "modules" / "demo"
    for layer in ModuleLayer:
        (base / layer.value).mkdir(parents=True, exist_ok=True)
    return tmp  # 返回源码根（含 tender_insight/）


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_real_source_has_no_layer_violations() -> None:
    """真实源码当前不存在分层违例（移除/无注入时通过）。"""
    src_root = Path(__file__).resolve().parents[2] / "src"
    assert find_layer_violations(src_root) == []


def test_reverse_dependency_is_detected_when_injected(tmp_path: Path) -> None:
    """注入一条 domain→application 反向依赖后，规则检查必须失败。"""
    src_root = _make_module_root(tmp_path)
    # 在 domain 层写入一条对 application 层的非法导入。
    _write(
        src_root / "tender_insight" / "modules" / "demo" / "domain" / "bad.py",
        "import tender_insight.modules.demo.application  # 反向依赖\n",
    )

    violations = find_layer_violations(src_root)
    assert len(violations) == 1, f"期望恰好 1 条违例，实际 {len(violations)}"
    v = violations[0]
    assert v.source_layer == ModuleLayer.DOMAIN
    assert v.target_layer == ModuleLayer.APPLICATION
    assert v.imported_module == "tender_insight.modules.demo.application"


def test_passes_after_reverse_dependency_removed(tmp_path: Path) -> None:
    """移除反向依赖（写入合法的同层/向下导入）后，规则检查通过。"""
    src_root = _make_module_root(tmp_path)
    # domain 层只导入标准库与同层模块，不构成反向依赖。
    _write(
        src_root / "tender_insight" / "modules" / "demo" / "domain" / "ok.py",
        "import dataclasses  # 标准库，合法\n",
    )

    assert find_layer_violations(src_root) == []


def test_allowed_forward_dependencies_pass(tmp_path: Path) -> None:
    """正向依赖（api→application、application→domain、infrastructure→domain）通过。"""
    src_root = _make_module_root(tmp_path)
    _write(
        src_root / "tender_insight" / "modules" / "demo" / "api" / "routes.py",
        "import tender_insight.modules.demo.application\n",
    )
    _write(
        src_root / "tender_insight" / "modules" / "demo" / "application" / "usecase.py",
        "import tender_insight.modules.demo.domain\n",
    )
    _write(
        src_root / "tender_insight" / "modules" / "demo" / "infrastructure" / "adapter.py",
        "import tender_insight.modules.demo.domain\n",
    )

    assert find_layer_violations(src_root) == []
