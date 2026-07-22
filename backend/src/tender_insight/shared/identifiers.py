"""业务标识值对象（A-007）。

SPEC.md 第 7.2 节要求业务 ID 使用 UUID。本模块提供统一的 UUID 值对象与
稳定错误类型，供各业务模块派生强类型 ID（如 ProjectId、DocumentVersionId），
避免裸字符串在模块间传递导致归属混淆。

仅依赖标准库 uuid，保持可被 domain 层安全导入（不引入框架耦合）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


class InvalidUuidError(ValueError):
    """UUID 解析失败时抛出的稳定错误。

    派生自 ValueError，并使用固定错误码标识（见 shared/errors.py 错误目录），
    使 API 层能将其映射为统一的 Problem Details 响应而非依赖文案匹配。
    """

    # 稳定错误码，供错误契约复用（A-012）。
    code: str = "INVALID_UUID"


@dataclass(frozen=True, order=True)
class Uuid:
    """UUID 值对象。

    不可变且可排序（order=True），便于作为字典键、集合元素与稳定排序依据。
    内部以 uuid.UUID 存储，对外提供标准十六进制字符串表示。
    """

    value: uuid.UUID

    @classmethod
    def new(cls) -> Uuid:
        """生成一个新的随机（v4）UUID。"""
        return cls(uuid.uuid4())

    @classmethod
    def from_str(cls, raw: str) -> Uuid:
        """从字符串解析 UUID；非法输入抛出 InvalidUuidError。

        同时接受带连字符的标准形式与 32 位十六进制紧凑形式（uuid.UUID 原生支持），
        保证不同来源（URL、数据库、JSON）的合法 UUID 往返一致。
        """
        try:
            return cls(uuid.UUID(raw))
        except (ValueError, AttributeError, TypeError) as cause:
            # 将底层多种异常统一为稳定错误，避免调用方逐个捕获。
            raise InvalidUuidError(f"非法 UUID：{raw!r}") from cause

    def __str__(self) -> str:
        # 统一输出带连字符的标准形式，作为对外契约表示。
        return str(self.value)
