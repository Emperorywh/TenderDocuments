"""共享内核包。

承载跨模块复用、具有稳定语义的值对象、契约与工具。依据 PLAN.md 第 3.2 节，
shared 只接收“具有稳定语义且有两个以上真实消费者”的代码；不在此处堆放
全局 services/utils。

放置约定：
- 纯领域值对象（identifiers、business_time、money）仅依赖标准库，确保可被
  各模块 domain 层安全导入，不引入框架耦合；
- API/应用层契约（pagination、errors 等）可使用 Pydantic，但不被 domain 导入。
"""
