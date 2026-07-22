"""project 领域异常（纯领域层）。

领域异常不依赖框架；与 shared.state_transitions.InvalidTransitionError 一样，
保持纯 ValueError 子类，由应用/API 层映射为 Problem Details。
"""

from __future__ import annotations


class InvalidProjectDataError(ValueError):
    """项目数据非法（空名称、缺失地区/行业/类型等）时抛出的稳定错误。"""

    code: str = "INVALID_PROJECT_DATA"
