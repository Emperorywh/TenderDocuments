"""FileSecurityScanner 端口测试（C-020 独立验证）。

验证端口为纯接口，领域层不依赖具体扫描器。
"""

from __future__ import annotations

import ast
from pathlib import Path

from tender_insight.modules.document.application import (
    FileSecurityScanner,
    SecurityScanOutcome,
    SecurityScanResult,
)

PORT_FILE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "tender_insight"
    / "modules"
    / "document"
    / "application"
    / "__init__.py"
)


def test_port_module_is_pure() -> None:
    """端口模块不依赖杀毒 SDK 或外部库。"""
    tree = ast.parse(PORT_FILE.read_text(encoding="utf-8"))
    forbidden = {"clamd", "pyclamd", "virus_total_apis", "yara"}
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert not (roots & forbidden), f"端口依赖了扫描器 SDK：{roots & forbidden}"


def test_protocol_is_implementable() -> None:
    class AlwaysCleanScanner:
        def scan(self, data: bytes, *, filename: str, mime: str) -> SecurityScanOutcome:
            return SecurityScanOutcome(result=SecurityScanResult.CLEAN)

    scanner: FileSecurityScanner = AlwaysCleanScanner()
    outcome = scanner.scan(b"data", filename="x.pdf", mime="application/pdf")
    assert outcome.result == SecurityScanResult.CLEAN


def test_scan_results_distinct() -> None:
    assert SecurityScanResult.CLEAN != SecurityScanResult.SUSPICIOUS
