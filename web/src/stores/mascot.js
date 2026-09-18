import { reactive } from 'vue'

/**
 * 全局吉祥物与欢迎区占位锚点之间的共享测量。
 *
 * 这里不存放任何 DOM 引用以外的业务状态：它只负责把一个可见的锚点元素
 * 转成视口坐标，让 BotLayer 在页面切换时仍然能读到实时位置。
 */
export const mascotAnchor = reactive({ rect: null })

/** 吉祥物点击后弹出的半透明面板状态；面板组件与 BotLayer 共享。 */
export const mascotPanel = reactive({ open: false })

let node = null
let observer = null

function readRect() {
  if (!node) {
    mascotAnchor.rect = null
    return null
  }
  const r = node.getBoundingClientRect()
  const rect = { left: r.left, top: r.top, width: r.width, height: r.height }
  mascotAnchor.rect = rect
  return rect
}

/** 每帧直接读取一次当前矩形，用于页面切换中的连续位置更新。 */
export function getMascotAnchorRect() {
  return readRect()
}

export function bindMascotAnchor(el) {
  if (!el || node === el) return
  unbindMascotAnchor()
  node = el
  readRect()
  if (typeof ResizeObserver !== 'undefined') {
    observer = new ResizeObserver(() => readRect())
    observer.observe(el)
  }
}

export function unbindMascotAnchor() {
  if (observer) {
    observer.disconnect()
    observer = null
  }
  node = null
  mascotAnchor.rect = null
}
