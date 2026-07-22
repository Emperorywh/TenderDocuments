"""project 模块领域层。

纯领域模型与不变量，不导入 Web/ORM/队列/供应商 SDK。生命周期转换经
shared.state_transitions 校验，确保非法转换在领域层即被拒绝。
"""
