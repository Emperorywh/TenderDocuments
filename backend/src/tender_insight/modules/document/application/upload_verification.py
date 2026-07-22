"""上传完成对象校验（C-009）。

客户端通知上传完成后，后端在创建业务文件（DocumentVersion）前校验暂存对象：
存在性 + 实际大小与声明大小一致。任一不符即抛错，保证不创建业务文件（SPEC.md
第 8.3、11.1 节）。
"""

from __future__ import annotations

from tender_insight.modules.document.application import ObjectKey
from tender_insight.modules.document.domain.exceptions import UploadObjectError


def verify_uploaded_object(
    object_storage,
    object_key: str,
    declared_size_bytes: int,
) -> int:
    """校验上传对象存在且大小一致；返回实际大小，失败抛 UploadObjectError。

    object_key 为存储内路径（如 "quarantine/<uuid>"）。
    """
    from tender_insight.modules.document.application import ObjectCategory

    # 解析 "category/key" 为 ObjectKey；对象键由系统生成，格式受控。
    parts = object_key.split("/", 1)
    if len(parts) != 2:
        raise UploadObjectError(f"非法对象键：{object_key}")
    try:
        category = ObjectCategory(parts[0])
    except ValueError as cause:
        raise UploadObjectError(f"未知对象分区：{parts[0]}") from cause
    key = ObjectKey(category=category, key=parts[1])

    if not object_storage.exists(key):
        raise UploadObjectError(f"上传对象缺失：{object_key}")
    actual_size = object_storage.size(key)
    if actual_size != declared_size_bytes:
        raise UploadObjectError(
            f"上传对象大小不符：声明 {declared_size_bytes}，实际 {actual_size}"
        )
    return actual_size
