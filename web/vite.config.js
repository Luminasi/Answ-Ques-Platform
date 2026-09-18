import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // RAG 服务 (8001)：问答 / 会话
      '/api/answer': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      '/api/conversations': { target: 'http://127.0.0.1:8001', changeOrigin: true },
      // RAG 服务的 chunks 接口（预留）走独立前缀避免与文档服务冲突
      '/api/chunks': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/chunks\/(.+)/, '/api/docs/$1/chunks'),
      },
      // RAG 健康检查
      '/api/rag-health': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: () => '/api/health',
      },
      // 文档服务 (8000)：列表 + 全文 + 健康检查（兜底规则放最后）
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
