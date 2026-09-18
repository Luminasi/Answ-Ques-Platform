// 后端地址收敛：实际请求通过 Vite 代理转发（见 vite.config.js）
export const API = {
  // 文档服务（8000）
  docsList: () => '/api/docs',
  doc: (source) => `/api/docs/${source}`,
  docsHealth: () => '/api/health',
  // RAG 服务（8001）
  answer: () => '/api/answer',
  conversations: () => '/api/conversations',
  conversation: (id) => `/api/conversations/${id}`,
  messages: (id) => `/api/conversations/${id}/messages`,
  // chunks 预留接口：/api/chunks/q001.md -> 8001/api/docs/q001.md/chunks
  chunks: (source) => `/api/chunks/${source}`,
  ragHealth: () => '/api/rag-health',
}
