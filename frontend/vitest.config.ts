import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Vitest 配置（A-015）。
// 使用 jsdom 环境以支持 React 组件的 DOM 断言；与 vite.config.ts 共用 React
// 插件与 @ 别名，避免重复配置漂移。
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
