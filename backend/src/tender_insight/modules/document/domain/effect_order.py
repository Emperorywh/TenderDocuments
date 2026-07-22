"""文件生效顺序规则（C-023）。

按 SPEC.md 第 6.4 节，多个文件/版本间存在生效顺序：补遗、澄清、延期等后发布文件
优先级更高。本规则以确定性算法计算稳定生效顺序——相同输入重复计算结果一致。

排序键：发布日期升序（更早发布在前，缺日期排最后）、再按版本号升序、最后以版本 ID
作为稳定兜底，确保完全确定。显式替代关系（C-024）在后续覆盖。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from tender_insight.shared.identifiers import Uuid

# 排序用的“最晚”时间戳（带时区，与领域 aware 时间一致），让无发布日期的版本排在最后。
_NO_DATE_SENTINEL = datetime.max.replace(tzinfo=UTC)


@dataclass(frozen=True)
class EffectOrderInput:
    """参与生效顺序计算的版本描述。"""

    version_id: Uuid
    published_date: datetime | None
    version_number: int


def compute_effect_order(inputs: list[EffectOrderInput]) -> dict[Uuid, int]:
    """计算稳定生效顺序，返回 version_id -> 1-based 序号（序号小优先级高）。

    确定性：相同输入集合（任意顺序）重复计算得到相同序号映射。
    """
    # 以发布日期、版本号、版本 ID 字符串为键稳定排序；ID 作为兜底保证完全确定。
    ranked = sorted(
        inputs,
        key=lambda item: (
            item.published_date or _NO_DATE_SENTINEL,
            item.version_number,
            str(item.version_id),
        ),
    )
    return {item.version_id: index + 1 for index, item in enumerate(ranked)}
