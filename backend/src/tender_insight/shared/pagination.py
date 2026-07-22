"""统一分页与排序契约（A-010）。

SPEC.md 第 8.1 节要求列表接口统一分页、筛选和最大页大小。本模块提供：

- PageRequest：分页请求（页码、页大小、排序），校验页码 >=1 且页大小在
  [1, MAX_PAGE_SIZE] 之间，越界直接拒绝；
- SortField / SortDirection：稳定的排序描述；
- apply_sort：对内存中的映射列表做多键稳定排序，供只读投影测试复用；
- Page[T]：统一分页响应，含 items、total、页码与总页数。

本契约用于 API/应用层；不供 domain 层导入。
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Generic, Mapping, TypeVar

from pydantic import BaseModel, field_validator

# 列表接口最大页大小：超过即拒绝，防止一次性拉取过多数据（SPEC.md 第 8.1 节）。
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20

T = TypeVar("T")


class SortDirection(str, Enum):
    """排序方向，使用小写字符串值便于与查询参数一致。"""

    ASC = "asc"
    DESC = "desc"


class SortField(BaseModel):
    """单个排序字段；多字段按列表顺序表达主次键。"""

    field: str
    direction: SortDirection = SortDirection.ASC


class PageRequest(BaseModel):
    """统一分页请求。

    page 为 1 起始；page_size 受 MAX_PAGE_SIZE 上限约束，越界在模型校验阶段
    即被拒绝，避免在仓储层重复散落边界判断。
    """

    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    sort: list[SortField] = []

    @field_validator("page")
    @classmethod
    def _page_must_be_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("page 必须 >= 1")
        return value

    @field_validator("page_size")
    @classmethod
    def _page_size_in_range(cls, value: int) -> int:
        if value < 1 or value > MAX_PAGE_SIZE:
            raise ValueError(f"page_size 必须在 1..{MAX_PAGE_SIZE} 之间")
        return value

    @property
    def offset(self) -> int:
        """数据库/列表切片的起始偏移量（0 起始）。"""
        return (self.page - 1) * self.page_size


def apply_sort(items: list[Mapping[str, object]], sorts: list[SortField]) -> list[Mapping[str, object]]:
    """对映射列表做多键稳定排序。

    利用 Python sort 的稳定性，从最次要键向最主要键依次排序：每个字段按
    direction 升/降序排列，等值项保持原相对顺序，从而结果稳定可复现。
    """
    result = list(items)
    # 从最后一个排序字段（最次要）向前排序，保证主键优先级。
    for spec in reversed(sorts):
        result.sort(
            key=lambda item, f=spec.field: item.get(f),
            reverse=(spec.direction == SortDirection.DESC),
        )
    return result


class Page(BaseModel, Generic[T]):
    """统一分页响应。"""

    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        """总页数；total 为 0 时为 0 页。"""
        if self.total <= 0 or self.page_size <= 0:
            return 0
        return math.ceil(self.total / self.page_size)
