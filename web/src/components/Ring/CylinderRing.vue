<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  domains: { type: Array, required: true }, // [{key, zh, color, desc, count, ids}]
})
const emit = defineEmits(['select'])

const stageEl = ref(null)
const ringEl = ref(null)
const cardEls = ref([])

const N = computed(() => props.domains.length)
const step = computed(() => 360 / N.value)

// 相机视角：观察者位于圆柱中心，卡片环绕四周、面朝观察者
let angle = 0
let velocity = 0.045   // 自动慢转速度
const IDLE = 0.045
let dragging = false
let lastX = 0
let moved = 0
let raf = 0
const frontIndex = ref(0)

function layout() {
  if (!ringEl.value) return
  const w = ringEl.value.clientWidth
  // 与 custom-spaces/index.html 同公式：相邻卡片沿切面留 w*0.073 的缝（300px 卡宽即 22px）
  const gap = w * 0.073
  const baseRadius = (w + gap) / (2 * Math.tan(Math.PI / N.value))
  // 放大圆柱半径：弧面铺开至屏幕两侧，缝隙随卡片加大保持紧凑（调大 = 更开、缝更大）
  const SPREAD = 1.35
  const radius = baseRadius * SPREAD
  cardEls.value.forEach((el, i) => {
    if (!el) return
    // rotateY(i*step) 后 translateZ(-radius)，卡片面向圆心
    el.style.transform = `rotateY(${i * step.value}deg) translateZ(${-radius}px)`
  })
  // 相机留在环外：透视距离取半径的 3 倍。index.html 的等效倍数是 2.16（12 张卡 30° 一步），
  // 这里 10 张卡是 36° 一步，倍数取大一点才能得到相同的平缓观感。调小 = 弧度更弯。
  stageEl.value?.style.setProperty('--ring-persp', `${Math.round(radius * 3)}px`)
}

function frame() {
  if (!dragging) {
    angle += velocity
    velocity += (IDLE - velocity) * 0.02
  }
  if (ringEl.value) {
    // 相机在环外，只旋转环本身
    ringEl.value.style.transform = `rotateY(${angle}deg)`
  }
  // 按每张卡片朝向观察者的角度实时计算明暗与层级
  cardEls.value.forEach((el, i) => {
    if (!el) return
    // 卡片朝向与视线方向的夹角（0 = 正对观察者）
    const rel = ((angle + i * step.value) % 360 + 360) % 360
    const deg = Math.min(rel, 360 - rel)          // 0..180
    const facing = Math.cos((deg * Math.PI) / 180) // 1 正对, -1 背对
    // 明度：正对最亮，背面最暗；z-index：正对最上层
    const light = 0.5 + 0.5 * Math.max(0, facing)
    el.style.opacity = String(0.28 + 0.72 * light)
    el.style.filter = `brightness(${(0.55 + 0.45 * light).toFixed(3)})`
    el.style.zIndex = String(Math.round(100 + facing * 100))
  })
  const norm = ((angle % 360) + 360) % 360
  // 最正对观察者的卡片满足 angle + i*step ≡ 0 (mod 360)
  frontIndex.value = (N.value - (Math.round(norm / step.value) % N.value)) % N.value
  raf = requestAnimationFrame(frame)
}

// ---- 拖拽（反向：内容随手走，如同转头环顾）----
function onDown(e) {
  dragging = true
  moved = 0
  lastX = e.clientX
  stageEl.value?.setPointerCapture(e.pointerId)
}
function onMove(e) {
  if (!dragging) return
  const dx = e.clientX - lastX
  lastX = e.clientX
  moved += Math.abs(dx)
  angle -= dx * 0.18   // 手向右拖 -> 视线向右转（内容向左移出）
  velocity = -dx * 0.18
}
function onUp() { dragging = false }

function onCardClick(d) {
  if (moved > 6) return
  emit('select', d)
}

onMounted(() => {
  layout()
  window.addEventListener('resize', layout)
  raf = requestAnimationFrame(frame)
})
onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('resize', layout)
})
</script>

<template>
  <div
    ref="stageEl"
    class="stage"
    :class="{ dragging }"
    @pointerdown="onDown"
    @pointermove="onMove"
    @pointerup="onUp"
    @pointercancel="onUp"
  >
    <div ref="ringEl" class="ring">
      <button
        v-for="(d, i) in domains"
        :key="d.key"
        :ref="(el) => (cardEls[i] = el)"
        class="domain-card"
        :class="{ front: i === frontIndex }"
        :style="{ '--card-color': d.color }"
        @click="onCardClick(d)"
      >
        <span class="card-glow" aria-hidden="true"></span>
        <span class="card-inner">
          <span class="card-count">{{ d.count }} 篇</span>
          <span class="card-zh">{{ d.zh }}</span>
          <span class="card-en">{{ d.key }}</span>
          <span class="card-desc">{{ d.desc }}</span>
          <span class="card-cta">点击查看文档 →</span>
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.stage {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  perspective: var(--ring-persp, 1300px);   /* 相机在环外，弧度平缓 */
  perspective-origin: 50% 46%;
  cursor: grab;
  touch-action: pan-y;
  user-select: none;
  overflow: hidden;
}
.stage.dragging { cursor: grabbing; }

/* 观察者在中心：先把相机向前推进 radius 距离，再反向旋转整个环 */
.ring {
  position: relative;
  transform-style: preserve-3d;
  --card-w: clamp(220px, 22vw, 360px);
  width: var(--card-w);
  height: calc(var(--card-w) * 1.28);
}

.domain-card {
  position: absolute;
  inset: 0;
  border: 1px solid var(--line-strong);
  border-radius: 16px;
  background:
    linear-gradient(165deg, rgba(255, 255, 255, 0.98), rgba(255, 255, 255, 0.86) 55%),
    rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  padding: 0;
  overflow: hidden;
  backface-visibility: hidden;    /* 环背面镜像卡片不穿透 */
  transition: border-color 0.3s, box-shadow 0.3s, opacity 0.3s;
  color: var(--text);
  text-align: left;
}
/* 明暗与层级由 JS 按朝向角实时驱动（内看视角），CSS 仅保留正面描边 */
.domain-card.front {
  border-color: var(--card-color);
  box-shadow:
    0 22px 60px rgba(16, 28, 44, 0.22),
    0 0 0 1px var(--card-color),
    0 0 48px color-mix(in srgb, var(--card-color) 30%, transparent);
}

.card-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(90% 60% at 50% -10%, color-mix(in srgb, var(--card-color) 32%, transparent), transparent 65%);
  opacity: 0;
  transition: opacity 0.35s;
}
.domain-card.front .card-glow { opacity: 1; }

.card-inner {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 1.15rem 1.1rem;
}
.card-count {
  align-self: flex-start;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 600;
  padding: 0.22rem 0.6rem;
  border-radius: var(--radius-pill);
  background: color-mix(in srgb, var(--card-color) 20%, transparent);
  color: var(--card-color);
  border: 1px solid color-mix(in srgb, var(--card-color) 45%, transparent);
}
.card-zh {
  font-family: var(--font-display);
  font-size: clamp(1.2rem, 1.9vw, 1.5rem);
  font-weight: 700;
  letter-spacing: -0.01em;
  margin-top: auto;
}
.card-en {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  color: var(--text-faint);
  margin-top: 0.25rem;
  letter-spacing: 0.02em;
}
.card-desc {
  font-size: 0.78rem;
  color: var(--text-dim);
  margin-top: 0.55rem;
}
.card-cta {
  margin-top: 0.9rem;
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--card-color);
  opacity: 0;
  transform: translateY(4px);
  transition: all 0.3s var(--ease-out);
}
.domain-card.front .card-cta { opacity: 1; transform: none; }

@media (max-width: 640px) {
  .ring { --card-w: 185px; }
}
@media (prefers-reduced-motion: reduce) {
  .domain-card, .card-glow, .card-cta { transition: none; }
}
</style>
