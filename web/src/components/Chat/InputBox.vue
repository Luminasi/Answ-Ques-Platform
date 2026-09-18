<script setup>
import { ref, computed, onMounted } from 'vue'
import { useChatStore } from '../../stores/chat'

const props = defineProps({
  centered: { type: Boolean, default: false }, // 空态居中模式
})

const chat = useChatStore()
const text = ref('')
const inputEl = ref(null)

const remaining = computed(() => 500 - text.value.length)
const canSend = computed(() => text.value.trim().length > 0 && !chat.streaming && remaining.value >= 0)

function send() {
  if (!canSend.value) return
  chat.ask(text.value)
  text.value = ''
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

onMounted(() => {
  if (props.centered) inputEl.value?.focus()
})

defineExpose({ focus: () => inputEl.value?.focus() })
</script>

<template>
  <div class="input-wrap" :class="{ centered }">
    <div class="input-box glass">
      <textarea
        ref="inputEl"
        v-model="text"
        class="input-field"
        placeholder="输入你的 Python 问题…（Enter 发送，Shift+Enter 换行）"
        rows="1"
        :disabled="chat.streaming"
        @keydown="onKeydown"
      ></textarea>
      <div class="input-footer">
        <span class="char-count" :class="{ over: remaining < 0 }">{{ remaining }}</span>
        <button class="btn btn-primary send-btn" :disabled="!canSend" @click="send">
          <svg v-if="!chat.streaming" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
          <span v-else class="spinner"></span>
          {{ chat.streaming ? '回答中' : '发送' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.input-wrap { padding: 0.6rem 0 0; }
.input-box {
  border-radius: var(--radius-card);
  padding: 0.75rem 0.9rem 0.6rem;
  transition: border-color 0.25s, box-shadow 0.25s;
}
.input-box:focus-within {
  border-color: rgba(217, 119, 6, 0.5);
  box-shadow: 0 0 0 1px rgba(217, 119, 6, 0.22), 0 8px 30px rgba(16, 28, 44, 0.12);
}

/* 居中模式：更大更醒目 */
.centered .input-box {
  border-radius: 18px;
  padding: 1rem 1.1rem 0.75rem;
  background: rgba(255, 255, 255, 0.85);
}
.centered .input-field { min-height: 56px; font-size: 1rem; }

.input-field {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text);
  font-family: var(--font-body);
  font-size: 0.94rem;
  line-height: 1.55;
  resize: none;
  min-height: 44px;
  max-height: 160px;
  field-sizing: content;
}
.input-field::placeholder { color: var(--text-faint); }
.input-field:disabled { opacity: 0.6; }
.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.35rem;
}
.char-count {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--text-faint);
}
.char-count.over { color: #dc2626; }
.send-btn { padding: 0.5rem 1.3rem; font-size: 0.85rem; }
.centered .send-btn { padding: 0.6rem 1.5rem; }
.spinner {
  width: 12px; height: 12px;
  border: 2px solid rgba(26, 18, 6, 0.3);
  border-top-color: #1a1206;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
