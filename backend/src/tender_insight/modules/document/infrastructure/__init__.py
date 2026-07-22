"""document 模块基础设施层。

承载对象存储适配器、文件仓储等。本层可依赖对象存储 SDK；不被 domain/application
反向导入。
"""

from __future__ import annotations
