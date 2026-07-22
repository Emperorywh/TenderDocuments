// App 组件测试（A-015 验证组件测试命令可运行）。
// 显式从 vitest 引入断言原语（globals=false），从 Testing Library 引入渲染工具。
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

import App from './App'

describe('App', () => {
  it('渲染系统主标题', () => {
    render(<App />)
    expect(
      screen.getByText('四川建筑施工招标文件智能解读与投标风险提示系统'),
    ).toBeInTheDocument()
  })

  it('渲染初始化占位说明', () => {
    render(<App />)
    expect(screen.getByText(/桌面端工程已初始化/)).toBeInTheDocument()
  })
})
