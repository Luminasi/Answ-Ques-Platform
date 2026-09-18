import { defineStore } from 'pinia'
import { reactive } from 'vue'
import { request } from '../api/request'
import { streamAnswer } from '../api/stream'
import { API } from '../config'

let msgSeq = 1

// 精排分是 0~1 的相关度（sigmoid）。命中的课程问题实测 ≥0.95；
// 全部低于阈值视为「资料库没找到」，前端直接屏蔽参考来源（后端不改）
const MIN_SOURCE_SCORE = 0.5

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [],      // 会话列表
    conversationId: null,   // 当前会话 id（null = 单轮模式）
    messages: [],           // 当前会话消息 [{id, role, content, citations, streaming, error}]
    streaming: false,       // 是否有流式回答进行中
    error: '',              // 全局错误提示
    loadingHistory: false,
  }),

  actions: {
    async fetchConversations() {
      try {
        const data = await request(API.conversations())
        this.conversations = data.conversations || []
      } catch (e) {
        this.error = e.message
      }
    },

    async createConversation(name) {
      const data = await request(API.conversations(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(name ? { name } : {}),
      })
      this.conversationId = data.id
      this.messages = []
      await this.fetchConversations()
      return data.id
    },

    async selectConversation(id) {
      this.conversationId = id
      this.loadingHistory = true
      this.messages = []
      try {
        const data = await request(API.messages(id))
        this.messages = data.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          // 历史消息同样过滤低相关来源，保持与流式一致的口径
          citations: (m.citations || []).filter((s) => Number(s.score) >= MIN_SOURCE_SCORE),
          streaming: false,
        }))
      } catch (e) {
        this.error = e.message
      } finally {
        this.loadingHistory = false
      }
    },

    // 新建空会话（首次进入时若无会话则创建）
    async ensureConversation() {
      await this.fetchConversations()
      if (this.conversationId == null) {
        if (this.conversations.length > 0) {
          await this.selectConversation(this.conversations[0].id)
        } else {
          await this.createConversation()
        }
      }
    },

    newChat() {
      // 点「新建会话」：创建新会话，上下文清零
      return this.createConversation()
    },

    async ask(question) {
      const q = question.trim()
      if (!q || this.streaming) return
      if (q.length > 500) {
        this.error = '问题不能超过 500 字'
        return
      }
      this.error = ''

      // 用户消息入列
      this.messages.push({ id: `u-${msgSeq++}`, role: 'user', content: q, citations: [] })

      // AI 占位消息（流式累加目标）
      // 必须用 reactive 包一层：流式回调闭包里改的是这个对象，
      // 裸对象被 push 进响应式数组后，改它的字段不会触发 Vue 重渲染
      // （数据进了 store，界面却一直停在「正在思考…」）。
      const aiMsg = reactive({
        id: `a-${msgSeq++}`,
        role: 'assistant',
        content: '',
        citations: [],
        streaming: true,
        thinking: true,
      })
      this.messages.push(aiMsg)
      this.streaming = true

      await streamAnswer(q, this.conversationId, {
        onMeta: (meta) => {
          // 不在此处清除 thinking：meta 早于检索/生成，提前清掉会出现空气泡，
          // thinking 持续到首个内容 delta 到来（见 onDelta）
          // 单轮模式后端回 null，不影响
          if (meta.conversation_id && this.conversationId == null) {
            this.conversationId = meta.conversation_id
          }
        },
        onDelta: (delta) => {
          aiMsg.thinking = false
          aiMsg.content += delta // delta 必须累加，不能覆盖
        },
        onSources: (sources) => {
          // 过滤低相关来源；全部被滤掉时 citations 为空，
          // SourceCard 自动隐藏，消息下方会显示「资料库中没有找到相关内容」
          aiMsg.citations = (sources || []).filter((s) => Number(s.score) >= MIN_SOURCE_SCORE)
        },
        onDone: (done) => {
          aiMsg.streaming = false
          aiMsg.thinking = false   // 兜底：流结束但无内容时也要关掉思考态
          aiMsg.id = done.assistant_message_id ?? aiMsg.id
          this.streaming = false
          this.fetchConversations() // 刷新侧边栏顺序
        },
        onError: (err) => {
          aiMsg.streaming = false
          aiMsg.thinking = false
          aiMsg.error = err.message || '回答生成失败'
          if (!aiMsg.content) aiMsg.content = ''
          this.streaming = false
        },
      })
    },
  },
})
