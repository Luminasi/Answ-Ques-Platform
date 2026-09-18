<script setup>
// 精简版 bloub 桌宠（引擎来自 github.com/jeremy-prt/bloub，MIT License）
// 只保留：默认动作循环播放 + 视线跟随鼠标。去掉了原项目的 i18n / 时间轴编辑依赖。
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, triggerRef } from 'vue'
import { NOTIF_BLUE } from '../../bot/decor'
import { BotEngine } from '../../bot/engine'
import { clamp, easings } from '../../bot/math'
import { EXPRESSION_BY_ID, DEFAULT_EXPRESSION } from '../../bot/expressions'
import { COLOR_BY_ID, SHAPE_BY_ID, DEFAULT_COLOR, DEFAULT_SHAPE, mixHex } from '../../bot/skins'
import { blockAt, defaultCycle } from '../../bot/cycles'
import { DEMI_VIEWBOX, RAYON } from '../../bot/repere'

const props = defineProps({
  size: { type: Number, default: 120 },
  shape: { type: String, default: DEFAULT_SHAPE },
  color: { type: String, default: DEFAULT_COLOR },
  expression: { type: String, default: DEFAULT_EXPRESSION },
  // 眼睛是身体上的「洞」，透出这个底色；应接近宠物身后的背景色
  paper: { type: String, default: '#16202e' },
  follow: { type: Boolean, default: true },
})

const R = RAYON
const VB = DEMI_VIEWBOX

const shapeRadii = computed(() => SHAPE_BY_ID.get(props.shape)?.radii ?? null)
const ink = computed(() => COLOR_BY_ID.get(props.color)?.hex ?? '#0a0a0c')
const expression = computed(() => EXPRESSION_BY_ID.get(props.expression) ?? null)

const cycle = defaultCycle().blocks
const engine = new BotEngine(R, cycle[0]?.state ?? 'idle', shapeRadii.value, expression.value)
const frame = shallowRef(engine.sample(0))
const uid = Math.random().toString(36).slice(2, 8)
const maskId = `pet-mask-${uid}`

let raf = 0
let clock = 0
let last = 0
let curBlock = -1

function tick(nowMs) {
  const now = nowMs / 1000
  if (!last) last = now
  clock += Math.min(now - last, 0.1) // 页面切走再回来时不跳帧
  last = now

  // 按默认循环推进状态块
  const { index } = blockAt(cycle, clock % totalDuration(cycle))
  if (index !== curBlock) {
    const b = cycle[index]
    if (curBlock === -1 || index < curBlock) engine.reset(b.state, clock)
    else engine.setState(b.state, clock)
    curBlock = index
  }

  aim()
  frame.value = engine.sample(clock)
  triggerRef(frame)
  raf = requestAnimationFrame(tick)
}

function totalDuration(blocks) {
  return blocks.reduce((s, b) => s + b.duration, 0)
}

/* ---- 视线跟随（简化自原项目 gaze 逻辑） ---- */
const svg = ref(null)
let pointer = null
let aiming = false
let turnSince = 0
const TURN_TIME = 0.7

function onPointerMove(e) {
  if (e.pointerType === 'touch') return
  pointer = { x: e.clientX, y: e.clientY }
}
function onPointerLeave() { pointer = null }

function aim() {
  if (!props.follow) return
  const box = svg.value?.getBoundingClientRect()
  if (!box || box.width === 0) return
  if (!aiming) turnSince = clock
  const halfW = Math.max(1, window.innerWidth / 2)
  const halfH = Math.max(1, window.innerHeight / 2)
  engine.setLook(
    {
      yaw: pointer ? clamp(((pointer.x - (box.left + box.width / 2)) / halfW) * 40, -40, 40) : 0,
      pitch: pointer ? clamp(((pointer.y - (box.top + box.height / 2)) / halfH) * 30, -30, 30) : 0,
      mix: easings.easeOutQuint(clamp((clock - turnSince) / TURN_TIME)),
      spin: 0,
      wander: pointer ? 0 : 1,
    },
    clock
  )
  aiming = true
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
  window.addEventListener('pointerleave', onPointerLeave)
  raf = requestAnimationFrame(tick)
})
onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  window.removeEventListener('pointermove', onPointerMove)
  window.removeEventListener('pointerleave', onPointerLeave)
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
      <!-- 眼睛是身体上挖出的洞，自动被轮廓裁切 -->
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

    <!-- 轨道后半段：画在身体之前，被身体遮挡 -->
    <g fill="none" stroke-linecap="round">
      <path v-for="arc in frame.arcs" :key="`b${arc.id}`" :d="arc.back" :stroke="`url(#${uid}-${arc.id})`" :stroke-width="arc.width" :opacity="arc.opacity" />
    </g>

    <!-- 爆裂粒子（身体后方） -->
    <g v-if="frame.dotsBehind">
      <component :is="dot.d ? 'path' : 'circle'" v-for="(dot, i) in frame.dots" :key="`pb${i}`" v-bind="dotAttrs(dot)" />
    </g>

    <g :opacity="frame.bodyAlpha">
      <path :d="frame.bodyPath" :fill="paper" />
      <g :mask="`url(#${maskId})`">
        <rect :x="-VB" :y="-VB" :width="VB * 2" :height="VB * 2" :fill="ink" />
      </g>
    </g>

    <!-- 爆裂粒子（身体前方） -->
    <g v-if="!frame.dotsBehind">
      <component :is="dot.d ? 'path' : 'circle'" v-for="(dot, i) in frame.dots" :key="`pf${i}`" v-bind="dotAttrs(dot)" />
    </g>

    <circle v-if="frame.notif" :cx="frame.notif.x" :cy="frame.notif.y" :r="frame.notif.r" :fill="NOTIF_BLUE" />

    <!-- 轨道前半段 -->
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
