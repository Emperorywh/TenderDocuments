"""ADR 记录集结构验证（A-020）。

验证 docs/adr 下存在 ADR-001～ADR-014 共 14 份记录，且每份包含背景、决策、后果、
重评条件四要素。该测试保证决策记录对后续维护者可读、可审计。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ADR_DIR = REPO_ROOT / "docs" / "adr"

# ADR 编号 0001..0014 对应的文件名前缀。
EXPECTED_ADR_IDS = [f"{i:04d}" for i in range(1, 15)]

# 四要素标题（中文），允许以二级或三级标题出现。
REQUIRED_SECTIONS = ["背景", "决策", "后果", "重评条件"]


def _adr_files() -> dict[str, Path]:
    return {p.stem.split("-", 1)[0]: p for p in ADR_DIR.glob("*.md") if p.stem[0].isdigit()}


def test_all_14_adrs_exist() -> None:
    """ADR-001～ADR-014 共 14 份文件全部存在。"""
    files = _adr_files()
    missing = [aid for aid in EXPECTED_ADR_IDS if aid not in files]
    assert not missing, f"缺失 ADR：{missing}"


def test_each_adr_has_required_sections() -> None:
    """每份 ADR 包含背景、决策、后果、重评条件。"""
    files = _adr_files()
    for aid in EXPECTED_ADR_IDS:
        path = files[aid]
        text = path.read_text(encoding="utf-8")
        missing = [s for s in REQUIRED_SECTIONS if s not in text]
        assert not missing, f"{path.name} 缺少要素：{missing}"


def test_each_adr_has_status_and_date() -> None:
    """每份 ADR 含状态与日期，便于追踪生命周期。"""
    for path in ADR_DIR.glob("*.md"):
        if not path.stem[0].isdigit():
            continue
        text = path.read_text(encoding="utf-8")
        assert "状态" in text, f"{path.name} 缺少状态"
        assert re.search(r"日期", text), f"{path.name} 缺少日期"


def test_adr_index_exists() -> None:
    """存在索引 README 指向各 ADR。"""
    index = ADR_DIR / "README.md"
    assert index.exists(), "缺少 docs/adr/README.md 索引"
    text = index.read_text(encoding="utf-8")
    # 索引至少引用 14 份 ADR。
    for aid in EXPECTED_ADR_IDS:
        assert aid in text, f"索引未引用 ADR {aid}"
