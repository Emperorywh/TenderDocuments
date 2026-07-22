"""模块依赖规则的权威实现（A-006 交付物）。

本模块是分层依赖检查的唯一权威：导入扫描、层级判定与违例收集都集中在此，
供各架构测试复用，避免规则散落多处造成“重复逻辑”（PLAN.md 第 14 节）。

规则依据 PLAN.md 第 3.2、3.3 节的依赖方向：

    api ──▶ application ──▶ domain
    infrastructure ──▶ application / domain

即“高层可依赖低层，低层不得反向依赖高层”。具体：

- domain 不得导入 application、infrastructure、api（任何模块的）；
- application 不得导入 infrastructure、api；
- infrastructure 不得导入 api。

此外 domain 层不得导入 Web、ORM、队列或供应商 SDK（与 A-005 一致），
该第三方禁止集合也定义在本模块，作为唯一来源。

本模块仅依赖标准库（ast、pathlib、dataclasses、enum），保证规则检查本身
不耦合被检查的对象。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ModuleLayer(str, Enum):
    """模块内四层分层标识。值与目录名一致，便于按路径段判定。"""

    DOMAIN = "domain"
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"
    API = "api"


# 层级数值：越大越“高”。低层导入高层即构成反向依赖。
_LAYER_RANK: dict[ModuleLayer, int] = {
    ModuleLayer.DOMAIN: 0,
    ModuleLayer.APPLICATION: 1,
    ModuleLayer.INFRASTRUCTURE: 1,
    ModuleLayer.API: 2,
}

# domain 层禁止依赖的第三方根模块（Web、ORM、队列、供应商 SDK）。
FORBIDDEN_IN_DOMAIN: frozenset[str] = frozenset(
    {
        "fastapi",
        "starlette",
        "uvicorn",
        "sqlalchemy",
        "alembic",
        "psycopg",
        "sqlmodel",
        "celery",
        "redis",
        "kombu",
        "minio",
        "boto3",
        "paddleocr",
        "openai",
    }
)


@dataclass(frozen=True)
class ImportViolation:
    """一条依赖违例记录，含位置、被导入模块与原因，便于断言与报告。"""

    file: Path
    imported_module: str
    source_layer: ModuleLayer
    target_layer: ModuleLayer
    reason: str


@dataclass(frozen=True)
class ForbiddenImportViolation:
    """domain 层导入了被禁止的第三方框架/SDK。"""

    file: Path
    imported_root: str
    reason: str


def scan_imports(file_path: Path) -> list[str]:
    """返回单个源文件中所有 import 语句的完整点分模块名。

    同时覆盖 `import a.b` 与 `from a.b import c` 两种形式；
    使用 AST 解析而非正则，避免被字符串或动态导入绕过。
    """
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def layer_of_file(file_path: Path, src_root: Path) -> ModuleLayer | None:
    """根据文件在 modules/<module>/<layer>/ 下的位置判定其所属分层。

    非模块文件（shared、main.py 等）返回 None，不参与分层规则检查。
    """
    try:
        rel = file_path.relative_to(src_root)
    except ValueError:
        return None
    parts = rel.parts
    # 期望形如 tender_insight/modules/<module>/<layer>/...
    if len(parts) < 4 or parts[0] != "tender_insight" or parts[1] != "modules":
        return None
    try:
        return ModuleLayer(parts[3])
    except ValueError:
        return None


def _parse_internal_layer(module: str) -> ModuleLayer | None:
    """从 tender_insight.modules.<mod>.<layer>.... 形式解析目标分层。"""
    parts = module.split(".")
    # parts[0]=tender_insight, [1]=modules, [2]=<mod>, [3]=<layer>
    if len(parts) < 4 or parts[0] != "tender_insight" or parts[1] != "modules":
        return None
    try:
        return ModuleLayer(parts[3])
    except ValueError:
        return None


def find_layer_violations(src_root: Path) -> list[ImportViolation]:
    """扫描所有模块源文件，收集“低层反向依赖高层”的违例。

    src_root 指向包含 tender_insight/ 的目录（即 backend/src）。
    """
    violations: list[ImportViolation] = []
    pkg_root = src_root / "tender_insight" / "modules"
    if not pkg_root.exists():
        return violations

    for file_path in pkg_root.rglob("*.py"):
        source_layer = layer_of_file(file_path, src_root)
        if source_layer is None:
            continue
        for module in scan_imports(file_path):
            target_layer = _parse_internal_layer(module)
            if target_layer is None:
                continue
            # 同层互相导入不视为违例（如 domain 内部、application 内部）。
            if target_layer == source_layer:
                continue
            if _LAYER_RANK[target_layer] > _LAYER_RANK[source_layer]:
                violations.append(
                    ImportViolation(
                        file=file_path,
                        imported_module=module,
                        source_layer=source_layer,
                        target_layer=target_layer,
                        reason=(
                            f"{source_layer.value} 层不得反向依赖 "
                            f"{target_layer.value} 层"
                        ),
                    )
                )
    return violations


def find_forbidden_domain_imports(src_root: Path) -> list[ForbiddenImportViolation]:
    """扫描 domain 层源文件，收集对 Web/ORM/队列/供应商 SDK 的导入。"""
    violations: list[ForbiddenImportViolation] = []
    pkg_root = src_root / "tender_insight" / "modules"
    if not pkg_root.exists():
        return violations

    for file_path in pkg_root.rglob("*.py"):
        if layer_of_file(file_path, src_root) is not ModuleLayer.DOMAIN:
            continue
        for module in scan_imports(file_path):
            root = module.split(".")[0]
            if root in FORBIDDEN_IN_DOMAIN:
                violations.append(
                    ForbiddenImportViolation(
                        file=file_path,
                        imported_root=root,
                        reason=f"domain 层禁止依赖 {root}",
                    )
                )
    return violations
