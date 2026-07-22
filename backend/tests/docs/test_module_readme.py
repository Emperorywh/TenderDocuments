"""模块 README 模板验证（A-023）。

验证模板与示例模块 README 都包含职责、入口、状态、依赖、禁区五个小节，
使未参与实现者可据模板说明模块边界。
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "docs" / "module-readme-template.md"
EXAMPLE_README = REPO_ROOT / "backend" / "src" / "tender_insight" / "modules" / "example" / "README.md"

REQUIRED_SECTIONS = ["职责", "入口", "状态", "依赖", "禁区"]


@pytest.mark.parametrize("label,path", [("模板", TEMPLATE), ("示例模块", EXAMPLE_README)])
def test_readme_has_required_sections(label: str, path: Path) -> None:
    """模板与示例模块 README 均含五个必填小节。"""
    assert path.exists(), f"{label} README 缺失：{path}"
    text = path.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SECTIONS if s not in text]
    assert not missing, f"{label} README 缺少小节：{missing}"


def test_template_explains_usage() -> None:
    """模板说明如何复制使用。"""
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "复制" in text or "占位符" in text
