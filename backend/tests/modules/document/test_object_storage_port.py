"""ObjectStorage 端口测试（C-001 独立验证）。

验证端口为纯接口，application 与 domain 不导入 MinIO SDK 或具体存储实现。
"""

from __future__ import annotations

import ast
from pathlib import Path

from tender_insight.modules.document.application import (
    ObjectCategory,
    ObjectKey,
    ObjectStorage,
)

SRC_ROOT = Path(__file__).resolve().parents[3] / "src"

# 端口与领域层禁止依赖的对象存储 SDK / 云厂商库。
FORBIDDEN_OBJECT_SDKS = {
    "minio",
    "boto3",
    "botocore",
    "s3transfer",
    "aiobotocore",
}


def _imported_roots(file_path: Path) -> set[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_port_module_is_sdk_free() -> None:
    """端口模块不导入对象存储 SDK。"""
    port_file = (
        SRC_ROOT / "tender_insight" / "modules" / "document" / "application" / "__init__.py"
    )
    roots = _imported_roots(port_file)
    assert not (roots & FORBIDDEN_OBJECT_SDKS), f"端口模块依赖 SDK：{roots & FORBIDDEN_OBJECT_SDKS}"


def test_domain_and_application_do_not_import_object_sdk() -> None:
    """document 的 domain 与 application 层均不导入对象存储 SDK。"""
    offenders: list[str] = []
    for layer in ("domain", "application"):
        layer_dir = SRC_ROOT / "tender_insight" / "modules" / "document" / layer
        if not layer_dir.exists():
            continue
        for path in layer_dir.rglob("*.py"):
            bad = _imported_roots(path) & FORBIDDEN_OBJECT_SDKS
            if bad:
                offenders.append(f"{path.relative_to(SRC_ROOT)}: {sorted(bad)}")
    assert not offenders, "domain/application 导入了对象存储 SDK：\n" + "\n".join(offenders)


def test_object_key_path_uses_category_and_key() -> None:
    key = ObjectKey(category=ObjectCategory.ORIGINAL, key="abc-123")
    assert key.as_path() == "original/abc-123"


def test_object_storage_protocol_is_implementable() -> None:
    """端口可被任意实现满足（结构化类型）。"""

    class InMemoryStorage:
        def __init__(self) -> None:
            self._store: dict[str, bytes] = {}

        def put(self, key, data, *, content_type):  # noqa: ANN001
            self._store[key.as_path()] = data

        def get(self, key):  # noqa: ANN001
            return self._store[key.as_path()]

        def exists(self, key):  # noqa: ANN001
            return key.as_path() in self._store

        def delete(self, key):  # noqa: ANN001
            self._store.pop(key.as_path(), None)

        def move(self, source, destination):  # noqa: ANN001
            self._store[destination.as_path()] = self._store.pop(source.as_path())

        def presigned_get_url(self, key, *, expires_in_seconds):  # noqa: ANN001
            return f"https://example.local/{key.as_path()}?expires={expires_in_seconds}"

    storage: ObjectStorage = InMemoryStorage()
    obj = ObjectKey(category=ObjectCategory.REPORTS, key="r-1")
    storage.put(obj, b"data", content_type="application/pdf")
    assert storage.exists(obj)
    assert storage.get(obj) == b"data"
    assert storage.presigned_get_url(obj, expires_in_seconds=60).startswith("https://")
