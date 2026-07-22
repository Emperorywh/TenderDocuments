# frontend

桌面端 Web 应用目录。

## 职责

承载四川建筑施工招标文件智能解读与投标风险提示系统的桌面端单页应用，仅支持桌面端，以 1440px 宽度为主要设计基准。

## 技术基线

依据 `PLAN.md` 第 2.1 节：React 19、TypeScript、Vite、React Router、TanStack Query、React Hook Form、Zod、Ant Design、PDF.js、由 OpenAPI 生成的客户端、Vitest 与 Testing Library。

## 边界

- 不包含用户、组织、登录、注册、角色或权限相关页面或路由；
- 服务端状态全部由 TanStack Query 管理，不复制到全局 Store；
- 前端类型和客户端由 OpenAPI 生成，不手写重复 DTO。

具体工程初始化见 `TASKS.md` 的 `A-004` 及后续前端任务。
