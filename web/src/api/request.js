// 统一请求封装：处理 加载中 / 失败 / 空数据 三态
export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `请求失败 (${status})`)
    this.status = status
  }
}

export async function request(url, { timeout = 10000, ...options } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  try {
    const res = await fetch(url, { ...options, signal: controller.signal })
    if (!res.ok) {
      let detail = ''
      try {
        const body = await res.json()
        detail = body.detail || ''
      } catch { /* 非 JSON 响应体 */ }
      throw new ApiError(res.status, detail)
    }
    return await res.json()
  } catch (e) {
    if (e.name === 'AbortError') throw new ApiError(0, '请求超时，请检查后端服务')
    throw e
  } finally {
    clearTimeout(timer)
  }
}
