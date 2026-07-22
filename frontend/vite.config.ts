import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite 配置。
// 首版桌面端为单页应用，构建产物由 Nginx 托管（部署见阶段 K）。
// 解析别名 '@' 指向 src，便于后续 features/entities/shared 分层引用。
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  server: {
    // 开发服务器代理 /api 与健康检查到后端，避免跨域；生产由 Nginx 统一入口。
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
