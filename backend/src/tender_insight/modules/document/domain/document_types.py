"""document 领域类型（C-014 起）。

定义文件业务类型等共享枚举。SPEC.md 第 6.4 节要求操作人员确认文件类型：
招标文件、澄清、补遗、延期通知、附件或其他。
"""

from __future__ import annotations

from enum import StrEnum


class DocumentBusinessType(StrEnum):
    """文件业务类型（SPEC.md 第 6.4 节）。"""

    TENDER_DOC = "TENDER_DOC"
    CLARIFICATION = "CLARIFICATION"
    ADDENDUM = "ADDENDUM"
    EXTENSION_NOTICE = "EXTENSION_NOTICE"
    ATTACHMENT = "ATTACHMENT"
    OTHER = "OTHER"
