<script setup>
import { ref, watch, nextTick } from 'vue'
import { useChatStore } from '../../stores/chat'
import { useNotesStore } from '../../stores/notes'
import { renderMarkdown } from '../../api/markdown'
import SourceCard from './SourceCard.vue'

const chat = useChatStore()
const notes = useNotesStore()
const listEl = ref(null)

// 新消息 / 流式内容更新时自动滚到底部
watch(
  () => [chat.messages.length, chat.messages[chat.messages.length - 1]?.content],
  async () => {
    await nextTick()
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
  }
)

const examples = [
  'Python 中的列表和元组有什么区别？',
  '如何使用 try-except 处理文件读取异常？',
  '解释一下 Python 的类和继承',
  'for 循环和 while 循环分别适合什么场景？',
]

function askExample(q) {
  chat.ask(q)
}

function saveNote(msg) {
  // 找到该 AI 消息对应的用户问题
  const idx = chat.messages.findIndex((m) => m.id === msg.id)
  const question = idx > 0 ? chat.messages[idx - 1].content : ''
  notes.add({ question, answer: msg.content, source: msg.citations?.[0]?.source || '' })
}
</script>

<template>
  <div ref="listEl" class="msg-list" data-scrollable>
    <div v-if="chat.loadingHistory" class="history-loading">加载会话历史…</div>

    <!-- 消息流 -->
    <div v-for="msg in chat.messages" :key="msg.id" class="msg-row" :class="msg.role">
      <div class="msg-bubble">
        <div v-if="msg.role === 'assistant'" class="msg-avatar">AI</div>
        <div class="msg-content">
          <template v-if="msg.role === 'assistant'">
            <div v-if="msg.thinking || (msg.streaming && !msg.content && !msg.error)" class="thinking">
              <span class="dot-pulse"></span>正在思考…
            </div>
            <div v-if="msg.content" class="md" v-html="renderMarkdown(msg.content)"></div>
            <span v-if="msg.streaming && msg.content" class="cursor">▍</span>
            <div v-if="msg.error" class="msg-error">{{ msg.error }}</div>
            <SourceCard :sources="msg.citations" />
            <div v-if="!msg.streaming && msg.content" class="msg-actions">
              <button class="action-btn" @click="saveNote(msg)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                存笔记
              </button>
            </div>
            <div v-if="!msg.streaming && msg.citations && msg.citations.length === 0 && msg.content && !msg.error" class="no-source">
              资料库中没有找到相关内容
            </div>
          </template>
          <template v-else>
            <div class="user-text">{{ msg.content }}</div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.msg-list {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 0 1rem;
  min-height: 0;
  scroll-behavior: smooth;
}

/* 欢迎空态已移至 ChatScreen（输入框居中模式） */
.history-loading { text-align: center; color: var(--text-faint); padding: 2rem; font-size: 0.86rem; }

/* 消息气泡 */
.msg-row {
  margin-bottom: 1.3rem;
  display: flex;
  animation: msg-in 0.35s var(--ease-out);
}
@keyframes msg-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
.msg-row.user { justify-content: flex-end; }
.msg-bubble { display: flex; gap: 0.7rem; max-width: 88%; }
.msg-row.user .msg-bubble { flex-direction: row-reverse; }

.msg-avatar {
  width: 32px; height: 32px;
  flex-shrink: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--lake), #0e7490);
  display: grid;
  place-items: center;
  font-family: var(--font-display);
  font-size: 0.72rem;
  font-weight: 700;
  color: #fff;
}

.msg-content { min-width: 0; }
.msg-row.user .user-text {
  background: linear-gradient(120deg, rgba(245, 158, 11, 0.2), rgba(245, 158, 11, 0.1));
  border: 1px solid rgba(245, 158, 11, 0.3);
  padding: 0.7rem 1.05rem;
  border-radius: 16px 16px 4px 16px;
  font-size: 0.92rem;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-row.assistant .msg-content {
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: 4px 16px 16px 16px;
  padding: 0.85rem 1.1rem;
}

.thinking {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-dim);
  font-size: 0.86rem;
  padding: 0.2rem 0;
}
.dot-pulse {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--lake);
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse { 0%, 100% { opacity: 0.3; transform: scale(0.85); } 50% { opacity: 1; transform: scale(1.1); } }

.cursor { color: var(--lake); animation: blink 0.9s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }

.msg-error {
  margin-top: 0.5rem;
  padding: 0.55rem 0.85rem;
  border-radius: 10px;
  background: rgba(220, 38, 38, 0.08);
  border: 1px solid rgba(220, 38, 38, 0.3);
  color: #b91c1c;
  font-size: 0.83rem;
}

.msg-actions { margin-top: 0.6rem; display: flex; gap: 0.5rem; }
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.32rem 0.8rem;
  border-radius: var(--radius-pill);
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-faint);
  font-size: 0.75rem;
  transition: all 0.2s;
}
.action-btn:hover { color: var(--accent); border-color: rgba(217, 119, 6, 0.45); background: var(--accent-soft); }

.no-source {
  margin-top: 0.6rem;
  font-size: 0.78rem;
  color: var(--text-faint);
  font-style: italic;
}

@media (prefers-reduced-motion: reduce) {
  .msg-row { animation: none; }
}
</style>
