// Vitest 测试环境初始化（A-015）。
// 引入 jest-dom 提供的 DOM 断言匹配器（如 toBeInTheDocument），并通过
// '@testing-library/jest-dom/vitest' 适配 Vitest 的 expect。
//
// 因 vitest 配置采用 globals=false（显式导入断言原语），@testing-library/react
// 的自动 cleanup 不会触发，故在此显式注册 afterEach 清理 DOM，避免多个用例
// 间 DOM 累积导致 getByText 误判“找到多个元素”。
import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
})
