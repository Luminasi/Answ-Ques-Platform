<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useAppStore } from '../../stores/app'
import { useChatStore } from '../../stores/chat'
import { useDocsStore, DOMAIN_META } from '../../stores/docs'
import { mascotPanel } from '../../stores/mascot'
import MessageList from '../Chat/MessageList.vue'
import InputBox from '../Chat/InputBox.vue'

const app = useAppStore()
const chat = useChatStore()
const docs = useDocsStore()

const activeTab = ref('chunks')
const panelEl = ref(null)
const panelStyle = ref('')
const frameStyle = ref('')

const MIN_SCALE = 0.55
const MAX_SCALE = 1.8

const panel = reactive({
  x: 0,
  y: 0,
  w: 460,
  h: 640,
  scale: 1,
  initialized: false,
})

// 取当前会话中最近一次带有引用来源的助手回答；不累计历史中的所有来源。
const latestSources = computed(() => {
  for (let i = chat.messages.length - 1; i >= 0; i--) {
    const msg = chat.messages[i]
    if (msg.role === 'assistant' && msg.citations?.length) return msg.citations
  }
  return []
})

function domainLabel(source) {
  const key = docs.domainOfSource(source)
  return key ? (DOMAIN_META[key]?.zh || key) : '未知领域'
}

function isCurrent(source) {
  return docs.currentDoc?.source === source.source && docs.activeChunkIndex === source.chunk_index
}

const currentIndex = computed(() => latestSources.value.findIndex((s) => isCurrent(s)))

// 从课程文档界面打开时，优先显示已保存的历史对话与继续提问入口。
watch(
  () => mascotPanel.open,
  (open) => {
    if (open && docs.explorerOpen) activeTab.value = 'chat'
  }
)

function jump(source) {
  app.goTo(1)
  docs.jumpToChunk(source.source, source.chunk_index)
}

function goNext() {
  const arr = latestSources.value
  if (!arr.length) return
  const idx = currentIndex.value
  const next = idx < 0 ? 0 : (idx + 1) % arr.length
  jump(arr[next])
}

function goPrev() {
  const arr = latestSources.value
  if (!arr.length) return
  const idx = currentIndex.value
  const prev = idx <= 0 ? arr.length - 1 : idx - 1
  jump(arr[prev])
}

function close() {
  mascotPanel.open = false
}

/* ------------------------- 面板拖动 / 整体缩放 ------------------------- */
function applyStyles() {
  const outerW = panel.w * panel.scale
  const outerH = panel.h * panel.scale
  panelStyle.value = `left:${panel.x.toFixed(1)}px;top:${panel.y.toFixed(1)}px;width:${outerW.toFixed(1)}px;height:${outerH.toFixed(1)}px;`
  frameStyle.value = `width:${panel.w}px;height:${panel.h}px;transform:scale(${panel.scale});transform-origin:top left;`
}

function clampPanel() {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const margin = 8

  // 缩放也限制在视口内：内容始终整体可见。
  const maxScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, (vw - margin * 2) / panel.w, (vh - margin * 2) / panel.h))
  panel.scale = Math.min(Math.max(panel.scale, MIN_SCALE), maxScale)

  const outerW = panel.w * panel.scale
  const outerH = panel.h * panel.scale
  const maxX = Math.max(margin, vw - outerW - margin)
  const maxY = Math.max(margin, vh - outerH - margin)
  panel.x = Math.min(Math.max(panel.x, margin), maxX)
  panel.y = Math.min(Math.max(panel.y, margin), maxY)
  applyStyles()
}

function initPanel() {
  const vw = window.innerWidth
  const vh = window.innerHeight
  panel.w = Math.min(460, vw - 24)
  panel.h = Math.min(640, vh - 32)
  panel.scale = 1
  panel.x = vw < 640 ? 12 : Math.max(12, vw - panel.w - 100)
  panel.y = vw < 640 ? Math.max(12, vh - panel.h - 88) : Math.max(12, vh - panel.h - 24)
  panel.initialized = true
  clampPanel()
}

const drag = { mode: null, pointerId: null, startX: 0, startY: 0, origX: 0, origY: 0, startScale: 1, centerX: 0, centerY: 0 }

function startDrag(e) {
  if (e.button !== 0) return
  if (e.target.closest('button')) return
  drag.mode = 'move'
  drag.pointerId = e.pointerId
  drag.startX = e.clientX
  drag.startY = e.clientY
  drag.origX = panel.x
  drag.origY = panel.y
  capture(e)
}

function startScale(e) {
  if (e.button !== 0) return
  drag.mode = 'scale'
  drag.pointerId = e.pointerId
  drag.startX = e.clientX
  drag.startY = e.clientY
  drag.startScale = panel.scale
  drag.centerX = panel.x + (panel.w * panel.scale) / 2
  drag.centerY = panel.y + (panel.h * panel.scale) / 2
  capture(e)
}

function capture(e) {
  if (panelEl.value?.setPointerCapture) {
    try { panelEl.value.setPointerCapture(e.pointerId) } catch { /* noop */ }
  }
}

function onPanelPointerMove(e) {
  if (!drag.mode || e.pointerId !== drag.pointerId) return
  if (drag.mode === 'move') {
    panel.x = drag.origX + (e.clientX - drag.startX)
    panel.y = drag.origY + (e.clientY - drag.startY)
  } else if (drag.mode === 'scale') {
    const d0 = Math.max(14, Math.hypot(drag.startX - drag.centerX, drag.startY - drag.centerY))
    const d = Math.max(14, Math.hypot(e.clientX - drag.centerX, e.clientY - drag.centerY))
    panel.scale = drag.startScale * (d / d0)

    // 以面板中心为锚点缩放，四个角的操作逻辑一致。
    const outerW = panel.w * panel.scale
    const outerH = panel.h * panel.scale
    panel.x = drag.centerX - outerW / 2
    panel.y = drag.centerY - outerH / 2
  }
  clampPanel()
}

function endPanelDrag(e) {
  if (!drag.mode) return
  if (e.pointerId && e.pointerId !== drag.pointerId) return
  drag.mode = null
  release(e)
}

function cancelPanelDrag(e) {
  drag.mode = null
  release(e)
}

function release(e) {
  if (panelEl.value?.hasPointerCapture?.(e.pointerId)) {
    try { panelEl.value.releasePointerCapture(e.pointerId) } catch { /* noop */ }
  }
}

/* ------------------------- 外部关闭 / 键盘 ------------------------- */
function onWindowPointerDown(e) {
  if (!mascotPanel.open) return
  if (panelEl.value?.contains(e.target)) return
  if (e.target.closest?.('.mascot-layer')) return
  mascotPanel.open = false
}

function onKeydown(e) {
  if (e.key === 'Escape' && mascotPanel.open) mascotPanel.open = false
}

function onWindowResize() {
  clampPanel()
}

onMounted(() => {
  if (!panel.initialized) initPanel()
  window.addEventListener('pointerdown', onWindowPointerDown)
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('resize', onWindowResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', onWindowPointerDown)
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('resize', onWindowResize)
})
</script>

<template>
  <Transition name="panel">
    <section
      v-show="mascotPanel.open"
      ref="panelEl"
      class="mascot-panel glass"
      :style="panelStyle"
      aria-label="吉祥物助手面板"
      @pointermove="onPanelPointerMove"
      @pointerup="endPanelDrag"
      @pointercancel="cancelPanelDrag"
      @lostpointercapture="cancelPanelDrag"
    >
      <div class="panel-frame" :style="frameStyle">
        <header class="panel-head" @pointerdown="startDrag">
          <div class="panel-tabs" role="tablist">
            <button
              class="panel-tab"
              :class="{ on: activeTab === 'chunks' }"
              @click="activeTab = 'chunks'"
            >相关 Chunk</button>
            <button
              class="panel-tab"
              :class="{ on: activeTab === 'chat' }"
              @click="activeTab = 'chat'"
            >继续提问</button>
          </div>
          <button class="panel-close" @click="close" aria-label="关闭面板">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
          </button>
        </header>

        <div v-show="activeTab === 'chunks'" class="panel-body chunk-panel-body" data-scrollable>
          <div class="panel-title">本次回答命中的 Chunk</div>

          <div class="chunk-nav">
            <button class="nav-btn" :disabled="!latestSources.length" @click="goPrev">上一个</button>
            <span class="nav-info">{{ latestSources.length ? (currentIndex >= 0 ? currentIndex + 1 : 1) : 0 }} / {{ latestSources.length }}</span>
            <button class="nav-btn" :disabled="!latestSources.length" @click="goNext">下一个</button>
          </div>

          <div v-if="latestSources.length" class="chunk-options">
            <button
              v-for="s in latestSources"
              :key="`${s.rank}-${s.source}-${s.chunk_index}`"
              class="chunk-option"
              :class="{ current: isCurrent(s) }"
              @click="jump(s)"
            >
              <span class="chunk-rank">#{{ s.rank }}</span>
              <span class="chunk-main">
                <span class="chunk-source">{{ s.source }} <em>· {{ domainLabel(s.source) }}</em></span>
                <span class="chunk-meta">
                  第 {{ s.chunk_index ?? '?' }} 个 chunk
                  <span class="chunk-score">相关度 {{ Number(s.score).toFixed(2) }}</span>
                </span>
                <span class="chunk-snippet">{{ s.snippet }}</span>
              </span>
              <span v-if="isCurrent(s)" class="chunk-now">当前</span>
            </button>
          </div>
          <div v-else class="panel-empty">本次回答暂时没有可跳转的参考 chunk。</div>
        </div>

        <div v-show="activeTab === 'chat'" class="panel-body panel-chat">
          <div class="panel-chat-body">
            <MessageList />
          </div>
          <div class="panel-chat-input">
            <InputBox />
          </div>
        </div>
      </div>

      <!-- 缩放手柄独立在内容层之上，四个角均可操作，不会被 chunk 卡片拦截。 -->
      <div class="panel-corner corner-tl" @pointerdown.stop="startScale" aria-hidden="true"></div>
      <div class="panel-corner corner-tr" @pointerdown.stop="startScale" aria-hidden="true"></div>
      <div class="panel-corner corner-bl" @pointerdown.stop="startScale" aria-hidden="true"></div>
      <div class="panel-corner corner-br" @pointerdown.stop="startScale" aria-hidden="true"></div>
    </section>
  </Transition>
</template>

<style scoped>
.mascot-panel {
  position: fixed;
  left: 0;
  top: 0;
  z-index: 85;
  overflow: hidden;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(16, 28, 44, 0.12);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 24px 70px rgba(16, 28, 44, 0.22);
}

.panel-frame {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  padding: 0.65rem 0.8rem 0.55rem;
  border-bottom: 1px solid var(--line);
  cursor: move;
  touch-action: none;
  user-select: none;
}
.panel-tabs { display: flex; gap: 0.35rem; }
.panel-tab {
  border: none;
  background: transparent;
  color: var(--text-dim);
  font-size: 0.82rem;
  font-weight: 600;
  padding: 0.42rem 0.8rem;
  border-radius: var(--radius-pill);
  transition: all 0.2s var(--ease-out);
}
.panel-tab:hover { color: var(--text); background: var(--bg-soft); }
.panel-tab.on { color: #1a1206; background: linear-gradient(120deg, var(--accent), #ea7c1f); }

.panel-close {
  width: 30px; height: 30px;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: var(--bg-soft);
  color: var(--text-dim);
  display: grid;
  place-items: center;
  transition: all 0.2s;
}
.panel-close:hover { color: var(--text); background: var(--bg-strong); }

.panel-body { flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden; }
.panel-title { padding: 0.8rem 1rem 0.5rem; font-size: 0.78rem; color: var(--text-faint); font-weight: 700; letter-spacing: 0.04em; }
.chunk-panel-body { overflow-y: auto; }

.chunk-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 0.5rem 0.85rem 0.65rem;
}
.nav-btn {
  flex: 1;
  max-width: 120px;
  padding: 0.45rem 0.8rem;
  border-radius: var(--radius-pill);
  border: 1px solid var(--line);
  background: var(--bg-soft);
  color: var(--text);
  font-size: 0.8rem;
  font-weight: 600;
  transition: all 0.2s var(--ease-out);
}
.nav-btn:hover:not(:disabled) { border-color: rgba(2, 132, 199, 0.45); background: var(--lake-soft); }
.nav-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.nav-info { font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-faint); min-width: 52px; text-align: center; }

.chunk-options { display: flex; flex-direction: column; gap: 0.55rem; padding: 0 0.85rem 1rem; }

.chunk-option {
  display: flex;
  align-items: flex-start;
  gap: 0.7rem;
  padding: 0.75rem 0.8rem;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.55);
  color: var(--text);
  text-align: left;
  transition: all 0.2s var(--ease-out);
}
.chunk-option:hover {
  border-color: rgba(2, 132, 199, 0.45);
  background: var(--lake-soft);
  transform: translateY(-1px);
}
.chunk-option.current {
  border-color: rgba(217, 119, 6, 0.45);
  background: var(--accent-soft);
}
.chunk-rank {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--lake);
}
.chunk-option.current .chunk-rank { color: var(--accent); }
.chunk-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.2rem; }
.chunk-source { font-size: 0.86rem; font-weight: 700; }
.chunk-source em { font-style: normal; color: var(--text-dim); font-size: 0.75rem; }
.chunk-meta { display: flex; gap: 0.6rem; font-size: 0.72rem; color: var(--text-faint); }
.chunk-score { font-family: var(--font-mono); color: var(--text-dim); }
.chunk-snippet {
  font-size: 0.78rem;
  color: var(--text-dim);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.chunk-now {
  flex-shrink: 0;
  padding: 0.1rem 0.5rem;
  border-radius: var(--radius-pill);
  background: var(--accent);
  color: #1a1206;
  font-size: 0.68rem;
  font-weight: 700;
}
.panel-empty { padding: 2rem 1.2rem; text-align: center; color: var(--text-faint); font-size: 0.85rem; }

.panel-chat { overflow: hidden; }
.panel-chat-body { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.panel-chat-body :deep(.msg-list) { height: 100%; min-height: 0; padding: 1rem 0.6rem 0.8rem; }
.panel-chat-input { flex-shrink: 0; padding: 0.25rem 0.8rem 0.85rem; }

.panel-corner {
  position: absolute;
  width: 24px;
  height: 24px;
  z-index: 60;
  touch-action: none;
}
.corner-tl { left: 0; top: 0; cursor: nwse-resize; }
.corner-tr { right: 0; top: 0; cursor: nesw-resize; }
.corner-bl { left: 0; bottom: 0; cursor: nesw-resize; }
.corner-br { right: 0; bottom: 0; cursor: nwse-resize; }
.panel-corner::after {
  content: '';
  position: absolute;
  width: 10px;
  height: 10px;
  border-color: var(--line-strong);
  border-style: solid;
}
/* 直角刻度线：与面板的平角边框结构一致，不带圆弧 */
.corner-tl::after { left: 3px; top: 3px; border-width: 2px 0 0 2px; }
.corner-tr::after { right: 3px; top: 3px; border-width: 2px 2px 0 0; }
.corner-bl::after { left: 3px; bottom: 3px; border-width: 0 0 2px 2px; }
.corner-br::after { right: 3px; bottom: 3px; border-width: 0 2px 2px 0; }

.panel-enter-active, .panel-leave-active { transition: opacity 0.22s var(--ease-out), transform 0.22s var(--ease-out); }
.panel-enter-from, .panel-leave-to { opacity: 0; transform: translateY(12px) scale(0.98); }
</style>
