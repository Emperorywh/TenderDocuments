"""project 模块基础设施层。

承载 SQLAlchemy ORM Model 与仓储适配器。本层可依赖 ORM；不被 domain/application
反向导入。
"""
