// SSE 流解析：POST + fetch ReadableStream（EventSource 不支持 POST）
// 事件序列：meta -> message*(delta 累加) -> sources -> done | error
import { API } from '../config'
import { ApiError } from './request'

export async function streamAnswer(question, conversationId, handlers) {
  const { onMeta, onDelta, onSources, onDone, onError } = handlers
  let res
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 120000) // 120s 兜底
    res = await fetch(API.answer(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(
        conversationId ? { question, conversation_id: conversationId } : { question }
      ),
      signal: controller.signal,
    })
    // （A）流开始之前的错误：非 200 / JSON 响应
    const contentType = res.headers.get('content-type') || ''
    if (!res.ok || !contentType.includes('text/event-stream')) {
      let detail = `服务异常 (${res.status})`
      try {
        const body = await res.json()
        detail = body.detail || detail
      } catch { /* ignore */ }
      clearTimeout(timer)
      onError(new ApiError(res.status, detail))
      return
    }

    // （B）解析 SSE 帧
    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let currentEvent = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // 按空行切帧
      let idx
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) currentEvent = line.slice(6).trim()
          else if (line.startsWith('data:')) {
            let data
            try { data = JSON.parse(line.slice(5).trim()) } catch { continue }
            switch (currentEvent) {
              case 'meta': onMeta?.(data); break
              case 'message': onDelta?.(data.delta ?? ''); break
              case 'sources': onSources?.(data.sources ?? []); break
              case 'done': onDone?.(data); break
              case 'error': onError?.(new ApiError(200, data.detail || '生成出错')); break
            }
          }
        }
        currentEvent = ''
      }
    }
    clearTimeout(timer)
  } catch (e) {
    if (e.name === 'AbortError') onError?.(new ApiError(0, '响应超时（120s），请重试'))
    else onError?.(e)
  }
}
