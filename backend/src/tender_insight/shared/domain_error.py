"""纯领域错误基类（无框架依赖）。

所有领域异常继承本基类，携带稳定 code、http_status、title 与 detail。本模块
仅依赖标准库，使领域层（domain、state_transitions 等）可安全抛出领域错误，
由 shared.errors 的处理器统一映射为 Problem Details（SPEC.md 第 8.1 节）。

code 为稳定错误码字符串（取值见 shared.error_codes.ErrorCode）；http_status
为该类错误对应的 HTTP 状态码；title 为简短标题；detail 为具体说明。
"""

from __future__ import annotations


class DomainError(Exception):
    """领域错误基类。子类固定 code、http_status、title。"""

    code: str = "DOMAIN_ERROR"
    http_status: int = 400
    title: str = "领域错误"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
