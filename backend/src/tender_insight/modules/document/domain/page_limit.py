"""单项目页数限制（C-028）。

SPEC.md 第 3.2 节：单项目全部有效输入合计不超过 500 页，且“页数是业务验收的硬
限制”。第 500 页允许，第 501 页被明确拒绝纳入分析。限额来自强类型配置（max_project_pages，
默认 500），领域不硬编码。
"""

from __future__ import annotations

from tender_insight.modules.document.domain.exceptions import FileLimitExceededError


def assert_project_pages(current_pages: int, adding_pages: int, *, max_pages: int) -> int:
    """校验项目页数：current + adding 超过 max_pages 则抛错。

    返回合计页数。第 max_pages 页允许，超出（第 max_pages+1 页）被拒绝。
    """
    total = current_pages + adding_pages
    if total > max_pages:
        raise FileLimitExceededError(
            f"项目页数 {total} 超过上限 {max_pages}（业务硬限制）"
        )
    return total
