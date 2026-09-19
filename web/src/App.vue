<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useAppStore } from './stores/app'
import { useChatStore } from './stores/chat'
import { useDocsStore } from './stores/docs'
import { API } from './config'
import ChatScreen from './views/ChatScreen.vue'
import RingScreen from './views/RingScreen.vue'
import BotLayer from './components/Bot/BotLayer.vue'
import BotPanel from './components/Bot/BotPanel.vue'

const app = useAppStore()
const chat = useChatStore()
const docs = useDocsStore()

const translate = computed(() => `translateY(-${app.currentScreen * 100}vh)`)
const overlayOpen = computed(() => docs.explorerOpen || docs.readerOpen)

// ---- 滚轮吸附切换 ----
let locked = false
let touchStartY = 0

function go(dir) {
  const next = Math.max(0, Math.min(1, app.currentScreen + dir))
  if (next === app.currentScreen) return
  app.goTo(next)
  locked = true
  setTimeout(() => { locked = false }, 900)
}

function onWheel(e) {
  if (locked) return
  if (docs.explorerOpen || docs.readerOpen) return
  // 若光标在可滚动容器内且该容器可继续滚动，则不切屏
  const el = e.target.closest('[data-scrollable]')
  if (el) {
    const atTop = el.scrollTop <= 0
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 2
    if ((e.deltaY < 0 && !atTop) || (e.deltaY > 0 && !atBottom)) return
  }
  if (Math.abs(e.deltaY) < 8) return
  go(e.deltaY > 0 ? 1 : -1)
}

function onTouchStart(e) { touchStartY = e.touches[0].clientY }
function onTouchEnd(e) {
  if (locked) return
  if (docs.explorerOpen || docs.readerOpen) return
  const dy = touchStartY - e.changedTouches[0].clientY
  const el = e.target.closest('[data-scrollable]')
  if (el && el.scrollHeight > el.clientHeight) {
    const atTop = el.scrollTop <= 0
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 2
    if ((dy < 0 && !atTop) || (dy > 0 && !atBottom)) return
  }
  if (Math.abs(dy) < 50) return
  go(dy > 0 ? 1 : -1)
}

// ---- 健康检查 ----
async function checkHealth() {
  try {
    const res = await fetch(API.docsHealth())
    app.docsReady = res.ok
  } catch { app.docsReady = false }
  try {
    const res = await fetch(API.ragHealth())
    app.ragReady = res.ok
  } catch { app.ragReady = false }
}

onMounted(async () => {
  window.addEventListener('wheel', onWheel, { passive: true })
  window.addEventListener('touchstart', onTouchStart, { passive: true })
  window.addEventListener('touchend', onTouchEnd, { passive: true })
  await checkHealth()
  docs.fetchDocsList()
  chat.ensureConversation()
})

onBeforeUnmount(() => {
  window.removeEventListener('wheel', onWheel)
  window.removeEventListener('touchstart', onTouchStart)
  window.removeEventListener('touchend', onTouchEnd)
})
</script>

<template>
  <div class="screens" :style="{ transform: translate }">
    <div class="screen"><ChatScreen /></div>
    <div class="screen"><RingScreen /></div>
  </div>

  <!-- 屏幕指示器 -->
  <nav v-if="!overlayOpen" class="screen-dots" aria-label="屏幕切换">
    <button :class="{ on: app.currentScreen === 0 }" @click="go(app.currentScreen === 1 ? -1 : 0)" aria-label="对话屏"></button>
    <button :class="{ on: app.currentScreen === 1 }" @click="go(app.currentScreen === 0 ? 1 : 0)" aria-label="文档环屏"></button>
  </nav>

  <!-- 全局常驻吉祥物：独立于页面容器，页面切换时不随屏移动 -->
  <BotLayer v-if="!docs.readerOpen" />

  <!-- 吉祥物点击后半透明助手面板 -->
  <BotPanel v-if="!docs.readerOpen" />

  <!-- 全局错误 Toast -->
  <div v-if="chat.error" class="toast" @click="chat.error = ''">{{ chat.error }}</div>
</template>
