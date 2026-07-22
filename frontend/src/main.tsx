import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'

// 应用入口。
// 首版为单实例、单工作区、无应用鉴权（SPEC.md 第 4 节）：进入应用直接展示
// 业务内容，不渲染登录页或会话恢复流程；相关页面在阶段 I 任务中补全。
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
