"""工程可导入性冒烟测试（A-002 独立验证）。

验证按锁文件安装后，tender_insight 包与核心运行时依赖均可正常导入，
且声明的 Python 基线约束可被读取。该测试不涉及业务逻辑，业务测试随
对应任务补充。
"""


def test_package_importable() -> None:
    """tender_insight 包可被导入且暴露版本元数据。"""
    import tender_insight

    assert isinstance(tender_insight.__version__, str)
    assert tender_insight.__version__


def test_runtime_dependencies_importable() -> None:
    """阶段 A/B/D 所依赖的核心运行时库均可导入。"""
    import alembic
    import celery
    import fastapi
    import httpx
    import jinja2
    import pydantic
    import pydantic_settings
    import redis
    import sqlalchemy
    import structlog

    # 仅断言模块对象存在，避免在导入阶段耦合具体版本字符串。
    for module in (
        fastapi,
        pydantic,
        pydantic_settings,
        sqlalchemy,
        alembic,
        celery,
        redis,
        httpx,
        structlog,
        jinja2,
    ):
        assert module is not None


def test_python_baseline_satisfied() -> None:
    """当前解释器满足 PLAN.md 第 2.2 节锁定的 >=3.12 基线。"""
    import sys

    assert sys.version_info >= (3, 12)
