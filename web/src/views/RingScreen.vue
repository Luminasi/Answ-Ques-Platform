<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useAppStore } from '../stores/app'
import { useDocsStore } from '../stores/docs'
import CylinderRing from '../components/Ring/CylinderRing.vue'
import DocList from '../components/Ring/DocList.vue'
import DocReader from '../components/Ring/DocReader.vue'
import DocExplorer from '../components/Ring/DocExplorer.vue'
// 背景图备用：恢复时取消模板中 bg-img 注释即可
// import meadowClouds from '../assets/bg/meadow-clouds.jpg'

const app = useAppStore()
const docs = useDocsStore()

const scrollEl = ref(null)
const hintGone = ref(false)
const previewSources = computed(() => (
  docs.chapterPreviews.flatMap((chapter) => chapter.items.map((item) => item.source))
))

function onSelect(domain) {
  docs.openDomain(domain.key)
}

function gotoChat() {
  app.goTo(0)
}

function onScroll() {
  hintGone.value = (scrollEl.value?.scrollTop || 0) > 40
}

// 长页面各区块滚动入场：进入视口即淡入上浮（复用全局 .reveal 类）
let io
onMounted(() => {
  docs.ensureTitles(previewSources.value)
  const els = scrollEl.value?.querySelectorAll('.reveal') || []
  if ('IntersectionObserver' in window) {
    io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting) {
          en.target.classList.add('in')
          io.unobserve(en.target)
        }
      })
    }, { threshold: 0.18 })
    els.forEach((el) => io.observe(el))
  } else {
    els.forEach((el) => el.classList.add('in'))
  }
})

onBeforeUnmount(() => io?.disconnect())
</script>

<template>
  <section class="ring-screen">
    <!-- 背景：纯白（草原云海图片备用，取消下行注释恢复） -->
    <div class="bg-scene" aria-hidden="true">
      <!-- <img class="bg-img" :src="meadowClouds" alt="" /> -->
      <!-- 深色遮罩随图片背景备用，白底下关闭 -->
      <!-- <div class="bg-scrim"></div> -->
    </div>

    <!-- 可滚动的长页面（环作第一屏 Hero，往下是统计 + CTA） -->
    <div ref="scrollEl" class="ring-scroll" data-scrollable @scroll="onScroll">
      <!-- 第一屏 · Hero：满屏 3D 环 -->
      <div class="hero">
        <header class="ring-head">
          <h2 class="ring-title">课程知识图谱</h2>
          <p class="ring-sub">拖动圆环，探索 10 个 Python 知识领域 · 共 {{ docs.stats.total }} 篇答疑文档</p>
        </header>

        <CylinderRing :domains="docs.domains" @select="onSelect" />

        <div class="scroll-hint" :class="{ gone: hintGone }" aria-hidden="true">
          <span class="hint-line"></span>
          <span class="hint-text">向下滚动</span>
        </div>
      </div>

      <!-- 使用数据统计 -->
      <section class="stats-sec">
        <p class="eyebrow reveal" :style="{ '--rd': '0s' }">By the numbers</p>
        <h3 class="sec-title reveal" :style="{ '--rd': '0.08s' }">知识库一览</h3>
        <div class="stats-grid">
          <div class="stat-card glass reveal" :style="{ '--rd': '0.12s' }">
            <span class="stat-num">{{ docs.stats.domains }}</span>
            <span class="stat-label">知识领域</span>
          </div>
          <div class="stat-card glass reveal" :style="{ '--rd': '0.2s' }">
            <span class="stat-num">{{ docs.stats.total }}</span>
            <span class="stat-label">答疑文档</span>
          </div>
          <div class="stat-card glass reveal" :style="{ '--rd': '0.28s' }">
            <span class="stat-num">{{ docs.stats.maxDomainCount }}</span>
            <span class="stat-label">最大领域篇数</span>
          </div>
          <div class="stat-card glass reveal" :style="{ '--rd': '0.36s' }">
            <span class="stat-num">{{ docs.stats.avgPerDomain }}</span>
            <span class="stat-label">平均每领域</span>
          </div>
        </div>
      </section>

      <!-- 章节化文档浏览 -->
      <section class="docs-sec">
        <div class="docs-head">
          <p class="eyebrow reveal" :style="{ '--rd': '0s' }">Course documentation</p>
          <h3 class="sec-title reveal" :style="{ '--rd': '0.08s' }">按章节浏览文档</h3>
          <p class="docs-sub reveal" :style="{ '--rd': '0.14s' }">
            从 10 个知识章节进入，快速定位代表性知识点与完整答疑文档。
          </p>
        </div>

        <div class="chapter-grid">
          <article
            v-for="(chapter, index) in docs.chapterPreviews"
            :key="chapter.key"
            class="chapter-card reveal"
            :style="{ '--chapter-color': chapter.color, '--rd': `${0.1 + index * 0.035}s` }"
          >
            <header class="chapter-head">
              <span class="chapter-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="chapter-count">{{ chapter.count }} 篇</span>
            </header>
            <h4 class="chapter-title">{{ chapter.zh }}</h4>
            <p class="chapter-desc">{{ chapter.desc }}</p>
            <ul class="preview-list">
              <li v-for="item in chapter.items" :key="item.source">
                <span class="preview-dot"></span>
                <span class="preview-title" :class="{ loading: !item.title }">
                  {{ item.title || '知识点加载中' }}
                </span>
              </li>
            </ul>
            <button class="more-btn" @click="docs.openExplorer(chapter.key)">
              更多
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6"/>
              </svg>
            </button>
          </article>
        </div>
      </section>

      <!-- 底部提问 CTA -->
      <section class="cta-sec">
        <div class="cta-card glass reveal" :style="{ '--rd': '0s' }">
          <h3 class="cta-title">找不到答案？直接问 AI。</h3>
          <p class="cta-sub">把问题丢给 AI 助教，基于全部 {{ docs.stats.total }} 篇答疑文档即时作答。</p>
          <button class="btn btn-primary cta-btn" @click="gotoChat">开始提问</button>
        </div>
        <footer class="ring-footer">课程答疑平台 · {{ docs.stats.total }} 篇文档 · 本地大模型驱动</footer>
      </section>
    </div>

    <!-- 右侧滑入的文档列表（保持固定覆盖层，不随长页面滚动） -->
    <DocList />

    <!-- 全文阅读器 -->
    <DocReader />

    <!-- 章节文档展示界面 -->
    <DocExplorer />
  </section>
</template>

<style scoped>
.ring-screen {
  height: 100%;
  position: relative;
  overflow: hidden;
}

/* 内层滚动容器：环是第一屏，往下可滚到统计与 CTA */
.ring-scroll {
  height: 100%;
  overflow-y: auto;
  scroll-behavior: smooth;
}

/* 滚动显现 + 淡入上移：全局 .reveal 基础上加逐项错峰延迟 */
.reveal {
  transition-delay: var(--rd, 0s);
  transition-timing-function: var(--ease-out);
}

.bg-scene { position: absolute; inset: 0; z-index: -1; overflow: hidden; background: #fff; }
.bg-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 20%;
}
.bg-scrim {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(to bottom, rgba(12, 20, 32, 0.42) 0%, rgba(12, 20, 32, 0.18) 40%, rgba(12, 20, 32, 0.62) 100%),
    radial-gradient(100% 70% at 50% 45%, transparent 35%, rgba(12, 20, 32, 0.35));
}

/* ---------- 第一屏 Hero ---------- */
.hero {
  position: relative;
  height: 100%;
  overflow: hidden;
}
.ring-head {
  text-align: center;
  padding: clamp(1.6rem, 4vh, 3rem) 1rem 0;
  pointer-events: none;
  position: relative;
  z-index: 5;
  animation: head-in 0.55s var(--ease-out);
}
@keyframes head-in {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: none; }
}
.ring-title {
  font-family: var(--font-display);
  font-size: clamp(1.6rem, 3.6vw, 2.5rem);
  font-weight: 700;
  letter-spacing: -0.02em;
}
.ring-sub {
  margin-top: 0.5rem;
  color: var(--text-dim);
  font-size: clamp(0.82rem, 1.3vw, 0.95rem);
}

/* 向下滚动提示 */
.scroll-hint {
  position: absolute;
  left: 50%;
  bottom: 1.4rem;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.45rem;
  color: var(--text-faint);
  font-size: 0.72rem;
  z-index: 6;
  pointer-events: none;
  transition: opacity 0.5s var(--ease-out);
}
.scroll-hint.gone { opacity: 0; }
.hint-line {
  position: relative;
  width: 1px;
  height: 30px;
  background: var(--line-strong);
  overflow: hidden;
}
.hint-line::after {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  background: var(--accent);
  animation: hint-drop 1.9s var(--ease-out) infinite;
}
@keyframes hint-drop {
  from { transform: translateY(-100%); }
  to { transform: translateY(100%); }
}

/* ---------- 数据统计 ---------- */
.stats-sec {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.4rem;
  padding: 4rem 1.5rem;
}
.eyebrow {
  font-family: var(--font-mono);
  font-size: 0.76rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--accent);
}
.sec-title {
  font-family: var(--font-display);
  font-size: clamp(1.5rem, 3.2vw, 2.2rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-bottom: 0.8rem;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  width: 100%;
  max-width: 900px;
}
.stat-card {
  border-radius: var(--radius-card);
  padding: 1.6rem 1.2rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  text-align: center;
}
.stat-num {
  font-family: var(--font-display);
  font-size: clamp(2rem, 4vw, 2.8rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text);
}
.stat-label {
  font-size: 0.82rem;
  color: var(--text-dim);
}

/* ---------- 章节化文档浏览 ---------- */
.docs-sec {
  min-height: 100vh;
  padding: 6rem 1.5rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2.4rem;
}
.docs-head {
  width: 100%;
  max-width: 1180px;
  text-align: center;
}
.docs-head .sec-title { margin-bottom: 0; }
.docs-sub {
  margin-top: 0.55rem;
  color: var(--text-dim);
  font-size: 0.9rem;
}
.chapter-grid {
  width: 100%;
  max-width: 1180px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}
.chapter-card {
  min-height: 255px;
  padding: 1.25rem 1.35rem 1.1rem;
  border: 1px solid var(--line);
  border-left: 4px solid var(--chapter-color);
  border-radius: var(--radius-card);
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 10px 34px rgba(16, 28, 44, 0.07);
  display: flex;
  flex-direction: column;
}
.chapter-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.chapter-index {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--chapter-color);
}
.chapter-count {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  padding: 0.18rem 0.58rem;
  border: 1px solid color-mix(in srgb, var(--chapter-color) 28%, transparent);
  border-radius: var(--radius-pill);
  background: color-mix(in srgb, var(--chapter-color) 8%, transparent);
  color: var(--chapter-color);
}
.chapter-title {
  font-family: var(--font-display);
  font-size: 1.2rem;
  line-height: 1.3;
  margin-top: 0.75rem;
}
.chapter-desc {
  margin-top: 0.25rem;
  color: var(--text-dim);
  font-size: 0.78rem;
}
.preview-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.42rem;
  margin-top: 1rem;
}
.preview-list li {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  min-width: 0;
  color: var(--text-dim);
  font-size: 0.82rem;
  line-height: 1.45;
}
.preview-dot {
  width: 5px;
  height: 5px;
  flex: 0 0 auto;
  margin-top: 0.48rem;
  border-radius: 50%;
  background: var(--chapter-color);
}
.preview-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.preview-title.loading { color: var(--text-faint); }
.more-btn {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: auto;
  padding: 0.45rem 0.8rem;
  border: 1px solid color-mix(in srgb, var(--chapter-color) 30%, transparent);
  border-radius: var(--radius-pill);
  background: color-mix(in srgb, var(--chapter-color) 8%, transparent);
  color: var(--chapter-color);
  font-size: 0.78rem;
  font-weight: 700;
  transition: transform 0.2s var(--ease-out), background 0.2s, border-color 0.2s;
}
.more-btn:hover {
  transform: translateY(-1px);
  background: color-mix(in srgb, var(--chapter-color) 14%, transparent);
  border-color: color-mix(in srgb, var(--chapter-color) 50%, transparent);
}

/* ---------- 底部 CTA ---------- */
.cta-sec {
  min-height: 82vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1.5rem;
}
.cta-card {
  max-width: 640px;
  width: 100%;
  border-radius: 20px;
  padding: 3rem 2rem;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.9rem;
}
.cta-title {
  font-family: var(--font-display);
  font-size: clamp(1.5rem, 3vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.02em;
}
.cta-sub {
  color: var(--text-dim);
  font-size: 0.95rem;
  max-width: 420px;
}
.cta-btn { margin-top: 0.5rem; }
.ring-footer {
  margin-top: 2.2rem;
  font-size: 0.78rem;
  color: var(--text-faint);
}

@media (max-width: 640px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .docs-sec { padding: 4.5rem 1rem; }
  .chapter-grid { grid-template-columns: 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .ring-head { animation: none; }
  .hint-line::after { animation: none; }
  .ring-scroll { scroll-behavior: auto; }
}
</style>
