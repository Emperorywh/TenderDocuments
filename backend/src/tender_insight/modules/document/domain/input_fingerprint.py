"""分析输入版本指纹（C-026）。

对分析输入版本集合计算稳定指纹：以 (version_id, sha256) 为成员，先按 version_id
排序再哈希，保证集合顺序无关；成员或内容变化则指纹变化。用于分析运行输入去重与
幂等（SPEC.md 第 9.3、11.3 节）。
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable


def compute_input_fingerprint(members: Iterable[tuple[str, str]]) -> str:
    """计算输入版本集合指纹。

    members 为 (version_id, sha256) 可迭代对象。先按 version_id 排序（顺序无关），
    再拼接并 SHA-256。返回十六进制摘要。
    """
    # 排序保证顺序无关；以稳定分隔符拼接避免歧义。
    normalized = sorted((vid, sha) for vid, sha in members)
    payload = "\n".join(f"{vid}:{sha}" for vid, sha in normalized)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
