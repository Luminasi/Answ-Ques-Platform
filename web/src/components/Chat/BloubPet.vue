<script setup>
// 全局常驻吉祥物的动画内核。
// 引擎来自 github.com/jeremy-prt/bloub（MIT License），这里只保留：
// 状态受外部驱动 + 动态形态/颜色/表情 + 平滑视线跟随。
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, triggerRef, watch } from 'vue'
import { NOTIF_BLUE } from '../../bot/decor'
import { BotEngine } from '../../bot/engine'
import { clamp } from '../../bot/math'
import { EXPRESSION_BY_ID, DEFAULT_EXPRESSION } from '../../bot/expressions'
import { COLOR_BY_ID, SHAPE_BY_ID, DEFAULT_COLOR, DEFAULT_SHAPE, mixHex } from '../../bot/skins'
import { DEMI_VIEWBOX, RAYON } from '../../bot/repere'

const props = defineProps({
  size: { type: Number, default: 120 },
  state: { type: String, default: 'idle' },
  shape: { type: String, default: DEFAULT_SHAPE },
  color: { type: String, default: DEFAULT_COLOR },
  expression: { type: String, default: DEFAULT_EXPRESSION },
  // 眼睛是身体上的「洞」，透出这个底色；浅色页面下保持深色瞳孔。
  paper: { type: String, default: '#223044' },
  follow: { type: Boolean, default: true },
})

const R = RAYON
const VB = DEMI_VIEWBOX

const shapeRadii = computed(() => SHAPE_BY_ID.get(props.shape)?.radii ?? null)
const ink = computed(() => COLOR_BY_ID.get(props.color)?.hex ?? '#0a0a0c')
const expression = computed(() => EXPRESSION_BY_ID.get(props.expression) ?? null)

const engine = new BotEngine(R, props.state, shapeRadii.value, expression.value)
const frame = shallowRef(engine.sample(0))
const uid = Math.random().toString(36).slice(2, 8)
const maskId = `pet-mask-${uid}`

let raf = 0
let clock = 0
let last = 0

// ---- 外部驱动状态、形态与表情，平滑过渡 ----
watch(shapeRadii, (radii) => {
  engine.setShape(radii, clock)
})
watch(expression, (expr) => {
  engine.setExpression(expr, clock)
})
watch(
  () => props.state,
  (state) => {
    if (state !== engine.state) engine.setState(state, clock)
  }
)

function tick(nowMs) {
  const now = nowMs / 1000
  if (!last) last = now
  clock += Math.min(now - last, 0.1)
  last = now

  aim()
  frame.value = engine.sample(clock)
  triggerRef(frame)
  raf = requestAnimationFrame(tick)
}

/* ---- 平滑视线跟随 ----
 * 与旧实现不同：不再拿整个窗口半径做灵敏度，而是以宠物自身为圆心，
 * 在小范围内达到最大偏角。这样鼠标靠近时眼睛立即有反应，远处也不越界。
 */
const svg = ref(null)
let pointer = null

const YAW_MAX = 18
const PITCH_BASE = 8
const PITCH_MAX = 14
const GAZE_RADIUS_X = 220
const GAZE_RADIUS_Y = 170
const LOOK_MORPH = 0.12

function onPointerMove(e) {
  if (e.pointerType === 'touch') return
  pointer = { x: e.clientX, y: e.clientY }
}
function onPointerLeave() { pointer = null }
function onWindowBlur() { pointer = null }

function aim() {
  if (!props.follow) {
    engine.setLook(null, clock)
    return
  }
  const box = svg.value?.getBoundingClientRect()
  if (!box || box.width === 0 || !pointer) {
    engine.setLook(null, clock)
    return
  }
  const cx = box.left + box.width / 2
  const cy = box.top + box.height / 2
  const nx = clamp((pointer.x - cx) / GAZE_RADIUS_X, -1, 1)
  const ny = clamp((pointer.y - cy) / GAZE_RADIUS_Y, -1, 1)
  engine.setLook(
    {
      yaw: nx * YAW_MAX,
      pitch: PITCH_BASE - ny * PITCH_MAX,
      mix: 1,
      spin: 0,
      wander: 0,
    },
    clock,
    LOOK_MORPH
  )
}

function dotAttrs(dot) {
  const fill = dot.color ?? (dot.depth === undefined ? ink.value : mixHex(props.paper, ink.value, dot.depth))
  const common = { fill, opacity: dot.opacity }
  return dot.d
    ? { ...common, d: dot.d, transform: `translate(${dot.x} ${dot.y}) rotate(${dot.rot ?? 0}) scale(${R})` }
    : { ...common, cx: dot.x, cy: dot.y, r: dot.r }
}

onMounted(() => {
  window.addEventListener('pointermove', onPointerMove, { passive: true })
  document.addEventListener('pointerleave', onPointerLeave)
  window.addEventListener('blur', onWindowBlur)
  raf = requestAnimationFrame(tick)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('pointermove', onPointerMove)
  document.removeEventListener('pointerleave', onPointerLeave)
  window.removeEventListener('blur', onWindowBlur)
})
</script>

<template>
  <svg
    ref="svg"
    :width="size"
    :height="size"
    :viewBox="`${-VB} ${-VB} ${VB * 2} ${VB * 2}`"
    role="img"
    aria-label="课程答疑小助手"
    class="bloub-pet"
  >
    <defs>
      <mask :id="maskId" maskUnits="userSpaceOnUse" :x="-VB" :y="-VB" :width="VB * 2" :height="VB * 2">
        <path :d="frame.bodyPath" fill="#fff" />
        <path v-for="(eye, i) in frame.eyes" :key="i" :d="eye.d" :transform="eye.matrix" :opacity="eye.alpha" fill="#000" />
        <circle v-if="frame.notch" :cx="frame.notch.x" :cy="frame.notch.y" :r="frame.notch.r" fill="#000" />
      </mask>
      <linearGradient
        v-for="arc in frame.arcs"
        :id="`${uid}-${arc.id}`"
        :key="arc.id"
        gradientUnits="userSpaceOnUse"
        :x1="arc.grad.x1" :y1="arc.grad.y1" :x2="arc.grad.x2" :y2="arc.grad.y2"
      >
        <stop v-for="(c, i) in arc.grad.stops" :key="i" :offset="i / (arc.grad.stops.length - 1)" :stop-color="c" />
      </linearGradient>
    </defs>

    <g fill="none" stroke-linecap="round">
      <path v-for="arc in frame.arcs" :key="`b${arc.id}`" :d="arc.back" :stroke="`url(#${uid}-${arc.id})`" :stroke-width="arc.width" :opacity="arc.opacity" />
    </g>

    <g v-if="frame.dotsBehind">
      <component :is="dot.d ? 'path' : 'circle'" v-for="(dot, i) in frame.dots" :key="`pb${i}`" v-bind="dotAttrs(dot)" />
    </g>

    <g :opacity="frame.bodyAlpha">
      <path :d="frame.bodyPath" :fill="paper" />
      <g :mask="`url(#${maskId})`">
        <rect :x="-VB" :y="-VB" :width="VB * 2" :height="VB * 2" :fill="ink" />
      </g>
    </g>

    <g v-if="!frame.dotsBehind">
      <component :is="dot.d ? 'path' : 'circle'" v-for="(dot, i) in frame.dots" :key="`pf${i}`" v-bind="dotAttrs(dot)" />
    </g>

    <circle v-if="frame.notif" :cx="frame.notif.x" :cy="frame.notif.y" :r="frame.notif.r" :fill="NOTIF_BLUE" />

    <g fill="none" stroke-linecap="round">
      <path v-for="arc in frame.arcs" :key="`f${arc.id}`" :d="arc.front" :stroke="`url(#${uid}-${arc.id})`" :stroke-width="arc.width" :opacity="arc.opacity" />
    </g>
  </svg>
</template>

<style scoped>
.bloub-pet {
  display: block;
  filter: drop-shadow(0 10px 24px rgba(0, 0, 0, 0.35));
}
</style>
