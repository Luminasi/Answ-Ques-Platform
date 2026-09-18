<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAppStore } from '../../stores/app'
import { useChatStore } from '../../stores/chat'
import { useDocsStore } from '../../stores/docs'
import { getMascotAnchorRect, mascotPanel } from '../../stores/mascot'
import { clamp } from '../../bot/math'
import BloubPet from '../Chat/BloubPet.vue'

const app = useAppStore()
const chat = useChatStore()
const docs = useDocsStore()

/* ----------------------------- 显示形态 ----------------------------- */
const visualState = ref('idle')
const bodyShape = ref('cercle')
const bodyColor = ref('orange')
const idleExpression = ref('neutre')
const faceExpression = ref('neutre')
const hovered = ref(false)
const dragging = ref(false)

const isEmpty = computed(() => chat.messages.length === 0 && !chat.loadingHistory)
const heroMode = computed(() => app.currentScreen === 0 && isEmpty.value)

// 状态优先级：拖动 > 错误 > 检索/加载 > 生成 > 成功 > 空闲
const behavior = computed(() => {
  if (dragging.value) return 'dragging'
  if (chat.phase === 'error') return 'error'
  if (chat.phase === 'retrieving' || chat.loadingHistory || docs.docLoading) return 'searching'
  if (chat.phase === 'generating') return 'generating'
  if (chat.phase === 'done') return 'success'
  return 'idle'
})

const effectiveExpression = computed(() => {
  if (hovered.value && behavior.value === 'idle' && !dragging.value) return 'attentif'
  return faceExpression.value
})

/* ----------------------------- 有序待机 ----------------------------- */
const microPool = ['wink', 'wide', 'notify']
const shapePool = ['cercle', 'galet', 'squircle', 'capsule', 'nuage', 'goutte']
const colorPool = ['orange', 'ambre', 'turquoise', 'bleu', 'violet', 'rose', 'vert']
const expressionPool = ['neutre', 'attentif', 'surpris', 'heureux', 'curieux', 'somnolent', 'mefiant']

function pickNext(pool, current) {
  const options = pool.filter((item) => item !== current)
  return options[Math.floor(Math.random() * options.length)] || pool[0]
}

let microTimer = 0
let appearanceTimer = 0
let oneShotTimer = 0
let clickActionTimer = 0

function clearIdleTimers() {
  clearTimeout(microTimer)
  clearTimeout(appearanceTimer)
}

function scheduleMicro(delay = 8000 + Math.random() * 7000) {
  clearTimeout(microTimer)
  microTimer = setTimeout(() => {
    if (behavior.value !== 'idle' || dragging.value) {
      scheduleMicro()
      return
    }
    visualState.value = pickNext(microPool, visualState.value)
    microTimer = setTimeout(() => {
      if (behavior.value === 'idle' && !dragging.value) visualState.value = 'idle'
      scheduleMicro()
    }, 1300 + Math.random() * 800)
  }, delay)
}

function scheduleAppearance(delay = 18000 + Math.random() * 12000) {
  clearTimeout(appearanceTimer)
  appearanceTimer = setTimeout(() => {
    if (behavior.value !== 'idle' || dragging.value) {
      scheduleAppearance()
      return
    }
    const channel = Math.floor(Math.random() * 3)
    if (channel === 0) bodyShape.value = pickNext(shapePool, bodyShape.value)
    else if (channel === 1) bodyColor.value = pickNext(colorPool, bodyColor.value)
    else {
      idleExpression.value = pickNext(expressionPool, idleExpression.value)
      if (behavior.value === 'idle' && !hovered.value) faceExpression.value = idleExpression.value
    }
    scheduleAppearance()
  }, delay)
}

watch(
  behavior,
  (next) => {
    clearIdleTimers()
    clearTimeout(oneShotTimer)
    clearTimeout(clickActionTimer)

    if (next === 'idle') {
      visualState.value = 'idle'
      faceExpression.value = idleExpression.value
      scheduleMicro()
      scheduleAppearance()
    } else if (next === 'dragging') {
      visualState.value = 'idle'
    } else if (next === 'searching') {
      visualState.value = 'searching'
      faceExpression.value = 'curieux'
    } else if (next === 'generating') {
      visualState.value = 'thinking'
    } else if (next === 'success') {
      visualState.value = 'notify'
      faceExpression.value = 'heureux'
      oneShotTimer = setTimeout(() => {
        if (chat.phase === 'done') chat.phase = 'idle'
      }, 1600)
    } else if (next === 'error') {
      visualState.value = 'alert'
      faceExpression.value = 'mefiant'
      oneShotTimer = setTimeout(() => {
        if (chat.phase === 'error') chat.phase = 'idle'
      }, 2200)
    }
  },
  { immediate: true }
)

/* ----------------------------- 全局位置与拖拽 ----------------------------- */
const BASE_SIZE = 110
const DOCK_SCALE = 0.66
const SMOOTH_TAU = 0.18

const layerStyle = ref('')

let curX = 0
let curY = 0
let curScale = 1
let posRaf = 0
let lastPosTime = 0

function targetFor() {
  const hero = heroMode.value
  const scale = hero ? 1 : DOCK_SCALE
  const w = BASE_SIZE * scale
  const h = BASE_SIZE * scale

  if (hero) {
    const rect = getMascotAnchorRect()
    if (rect) {
      return {
        x: rect.left + rect.width / 2 - w / 2,
        y: rect.top + rect.height / 2 - h / 2,
        scale,
      }
    }
  }

  const margin = window.innerWidth < 640 ? 12 : 24
  if (app.currentScreen === 0) {
    // 对话屏停靠在右上角空白区，避开右下角发送按钮和顶部状态栏。
    return {
      x: window.innerWidth - w - margin,
      y: window.innerWidth < 640 ? 76 : 88,
      scale,
    }
  }

  return {
    x: window.innerWidth - w - margin,
    y: window.innerHeight - h - margin,
    scale,
  }
}

function applyStyle() {
  layerStyle.value = `transform: translate3d(${curX.toFixed(2)}px, ${curY.toFixed(2)}px, 0) scale(${curScale.toFixed(3)});`
}

function posTick(now) {
  if (!lastPosTime) lastPosTime = now
  const dt = Math.min((now - lastPosTime) / 1000, 0.05)
  lastPosTime = now

  if (!dragging.value) {
    const target = targetFor()
    const k = 1 - Math.exp(-dt / SMOOTH_TAU)
    curX += (target.x - curX) * k
    curY += (target.y - curY) * k
    curScale += (target.scale - curScale) * k
    applyStyle()
  }

  posRaf = requestAnimationFrame(posTick)
}

const drag = { active: false, pointerId: null, startX: 0, startY: 0, baseX: 0, baseY: 0, moved: false }

function onPointerDown(e) {
  if (e.button !== 0) return
  dragging.value = true
  drag.active = true
  drag.pointerId = e.pointerId
  drag.startX = e.clientX
  drag.startY = e.clientY
  drag.baseX = curX
  drag.baseY = curY
  drag.moved = false
  if (e.currentTarget?.setPointerCapture) {
    try { e.currentTarget.setPointerCapture(e.pointerId) } catch { /* noop */ }
  }
}

function onPointerMove(e) {
  if (!drag.active || e.pointerId !== drag.pointerId) return
  const dx = e.clientX - drag.startX
  const dy = e.clientY - drag.startY
  if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true

  const size = BASE_SIZE * curScale
  const margin = 8
  curX = clamp(drag.baseX + dx, margin, window.innerWidth - size - margin)
  curY = clamp(drag.baseY + dy, margin, window.innerHeight - size - margin)
  applyStyle()
}

function finishDrag(e) {
  if (!drag.active) return
  if (e.pointerId && e.pointerId !== drag.pointerId) return
  const wasClick = !drag.moved
  drag.active = false
  dragging.value = false
  if (e.currentTarget?.hasPointerCapture?.(e.pointerId)) {
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* noop */ }
  }
  // 点击和拖动共用一个指针序列：位移极小视为点击。
  if (wasClick) {
    if (app.currentScreen === 0) {
      // 第一屏只做互动动作，不呼出对话框。
      mascotPanel.open = false
      playClickAction()
    } else {
      mascotPanel.open = !mascotPanel.open
    }
  }
}

function onPointerCancel(e) {
  drag.active = false
  dragging.value = false
  if (e.currentTarget?.hasPointerCapture?.(e.pointerId)) {
    try { e.currentTarget.releasePointerCapture(e.pointerId) } catch { /* noop */ }
  }
}

function onLostPointerCapture() {
  drag.active = false
  dragging.value = false
}

function playClickAction() {
  if (behavior.value !== 'idle') return
  visualState.value = 'orbit'
  clearTimeout(clickActionTimer)
  clickActionTimer = setTimeout(() => {
    if (behavior.value === 'idle' && !dragging.value) visualState.value = 'idle'
  }, 1700)
}

function onPointerEnter() { hovered.value = true }
function onPointerLeave() { hovered.value = false }

onMounted(() => {
  const initial = targetFor()
  curX = initial.x
  curY = initial.y
  curScale = initial.scale
  applyStyle()
  lastPosTime = 0
  posRaf = requestAnimationFrame(posTick)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(posRaf)
  clearIdleTimers()
  clearTimeout(oneShotTimer)
  clearTimeout(clickActionTimer)
})
</script>

<template>
  <div
    class="mascot-layer"
    :class="{ dragging, hovered }"
    :style="layerStyle"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="finishDrag"
    @pointercancel="onPointerCancel"
    @lostpointercapture="onLostPointerCapture"
    @pointerover="onPointerEnter"
    @pointerout="onPointerLeave"
  >
    <BloubPet
      :size="BASE_SIZE"
      :state="visualState"
      :shape="bodyShape"
      :color="bodyColor"
      :expression="effectiveExpression"
      :follow="!dragging"
      paper="#223044"
    />
  </div>
</template>

<style scoped>
.mascot-layer {
  position: fixed;
  left: 0;
  top: 0;
  width: 110px;
  height: 110px;
  z-index: 80;
  pointer-events: none;
  transform-origin: 0 0;
  will-change: transform;
}

/* 只有 SVG 本体接收指针，透明方块不会挡到页面点击。 */
.mascot-layer :deep(.bloub-pet) {
  pointer-events: auto;
  cursor: grab;
  touch-action: none;
  transition: transform 0.22s var(--ease-out);
}

.mascot-layer.dragging :deep(.bloub-pet) {
  cursor: grabbing;
  transform: rotate(-6deg) scale(1.06);
}

@media (prefers-reduced-motion: reduce) {
  .mascot-layer :deep(.bloub-pet) {
    transition: none;
  }
}
</style>
