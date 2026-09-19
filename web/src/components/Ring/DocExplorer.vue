<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useDocsStore, DOMAIN_META } from '../../stores/docs'
import { renderMarkdown } from '../../api/markdown'

const docs = useDocsStore()
const contentEl = ref(null)

const meta = computed(() => (
  DOMAIN_META[docs.explorerDomain] || { zh: docs.explorerDomain || '', color: '#475569' }
))
const articleHtml = computed(() => (
  docs.explorerDoc ? renderMarkdown(docs.explorerDoc.content) : ''
))
const articleTitle = computed(() => (
  docs.explorerDoc?.title || docs.titleOf(docs.explorerDoc?.source || '')
))

function chapterNumber(index) {
  return String(index + 1).padStart(2, '0')
}

function close() {
  docs.closeExplorer()
}

function onKeydown(e) {
  if (e.key === 'Escape' && docs.explorerOpen) close()
}

watch(
  () => docs.explorerDoc?.source,
  async () => {
    await nextTick()
    if (contentEl.value) contentEl.value.scrollTop = 0
  }
)

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Transition name="explorer">
    <section
      v-if="docs.explorerOpen"
      class="doc-explorer"
      role="dialog"
      aria-modal="true"
      aria-label="课程文档"
    >
      <header class="explorer-head">
        <button class="explorer-brand" @click="close">
          <span class="brand-mark" aria-hidden="true">
            <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z"/>
            </svg>
          </span>
          <span>课程答疑文档</span>
        </button>

        <div class="head-crumb">
          <span>文档目录</span>
          <span class="crumb-arrow">/</span>
          <strong>{{ meta.zh }}</strong>
        </div>

        <button class="explorer-close" @click="close" aria-label="关闭文档界面">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round">
            <path d="M18 6 6 18M6 6l12 12"/>
          </svg>
        </button>
      </header>

      <div class="explorer-layout">
        <aside class="explorer-nav">
          <div class="nav-head">
            <span>文档目录</span>
            <span>{{ docs.stats.total }} 篇</span>
          </div>
          <div class="nav-scroll" data-scrollable>
            <section v-for="(domain, index) in docs.domains" :key="domain.key" class="nav-chapter">
              <button
                class="chapter-row"
                :class="{ active: docs.explorerDomain === domain.key }"
                :style="{ '--chapter-color': domain.color }"
                :aria-expanded="docs.explorerDomain === domain.key && docs.explorerNavOpen"
                @click="docs.toggleExplorerDomain(domain.key)"
              >
                <span class="chapter-no">{{ chapterNumber(index) }}</span>
                <span class="chapter-name">{{ domain.zh }}</span>
                <span class="chapter-total">{{ domain.count }}</span>
                <svg class="chapter-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="m9 18 6-6-6-6"/>
                </svg>
              </button>

              <div
                v-if="docs.explorerDomain === domain.key && docs.explorerNavOpen"
                class="nav-docs"
                data-scrollable
              >
                <button
                  v-for="item in docs.explorerDocs"
                  :key="item.source"
                  class="nav-doc"
                  :class="{ active: docs.explorerDoc?.source === item.source }"
                  @click="docs.openExplorerDoc(item.source)"
                >
                  <span class="nav-doc-id">{{ String(item.id).padStart(3, '0') }}</span>
                  <span class="nav-doc-title">{{ item.title || '知识点加载中' }}</span>
                </button>
              </div>
            </section>
          </div>
        </aside>

        <main class="explorer-main">
          <div class="doc-toolbar">
          <div class="toolbar-crumb">
              <span>课程文档</span>
              <span>/</span>
              <span>{{ meta.zh }}</span>
              <span>/</span>
              <strong>{{ articleTitle }}</strong>
            </div>
          </div>

          <div ref="contentEl" class="doc-scroll" data-scrollable>
            <div v-if="docs.explorerDocLoading" class="doc-loading">
              <span class="loading-line wide"></span>
              <span class="loading-line"></span>
              <span class="loading-line"></span>
              <span class="loading-line short"></span>
            </div>
            <div v-else-if="docs.explorerDocError" class="doc-error">
              {{ docs.explorerDocError }}
            </div>
            <article v-else-if="docs.explorerDoc" class="md doc-article" v-html="articleHtml"></article>
            <div v-else class="doc-empty">请选择左侧章节中的文档</div>
          </div>
        </main>

        <aside class="explorer-rail">
          <div class="rail-head">本章知识点</div>
          <div class="rail-scroll" data-scrollable>
            <button
              v-for="item in docs.explorerDocs"
              :key="item.source"
              class="rail-item"
              :class="{ active: docs.explorerDoc?.source === item.source }"
              :style="{ '--chapter-color': meta.color }"
              @click="docs.openExplorerDoc(item.source)"
            >
              <span>{{ item.title || '知识点加载中' }}</span>
            </button>
          </div>
        </aside>
      </div>
    </section>
  </Transition>
</template>

<style scoped>
.doc-explorer {
  position: absolute;
  inset: 0;
  z-index: 70;
  background: rgba(255, 255, 255, 0.98);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.explorer-head {
  height: 64px;
  flex: 0 0 64px;
  display: grid;
  grid-template-columns: minmax(210px, 1fr) auto minmax(210px, 1fr);
  align-items: center;
  gap: 1rem;
  padding: 0 1.15rem;
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(16px);
}
.explorer-brand {
  justify-self: start;
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  border: 0;
  background: transparent;
  color: var(--text);
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 700;
}
.brand-mark {
  width: 31px;
  height: 31px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--text);
  color: #fff;
}
.head-crumb {
  justify-self: center;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
  color: var(--text-faint);
  font-size: 0.8rem;
}
.head-crumb strong {
  color: var(--text-dim);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.crumb-arrow { color: var(--line-strong); }
.explorer-close {
  justify-self: end;
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: 50%;
  background: var(--bg-soft);
  color: var(--text-dim);
  transition: all 0.2s;
}
.explorer-close:hover { color: var(--text); background: var(--bg-strong); }

.explorer-layout {
  min-height: 0;
  flex: 1;
  display: grid;
  grid-template-columns: 270px minmax(0, 1fr) 230px;
}
.explorer-nav {
  min-width: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--line);
  background: rgba(247, 248, 250, 0.78);
}
.nav-head {
  height: 48px;
  flex: 0 0 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1rem;
  border-bottom: 1px solid var(--line);
  color: var(--text-dim);
  font-size: 0.78rem;
  font-weight: 700;
}
.nav-head span:last-child {
  font-family: var(--font-mono);
  color: var(--text-faint);
  font-weight: 500;
}
.nav-scroll {
  min-height: 0;
  overflow-y: auto;
  padding: 0.6rem;
}
.nav-chapter + .nav-chapter { margin-top: 0.2rem; }
.chapter-row {
  width: 100%;
  min-height: 42px;
  display: grid;
  grid-template-columns: 25px minmax(0, 1fr) auto 16px;
  align-items: center;
  gap: 0.45rem;
  padding: 0.52rem 0.62rem;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--text-dim);
  text-align: left;
  transition: background 0.18s, color 0.18s;
}
.chapter-row:hover { background: var(--bg-soft); color: var(--text); }
.chapter-row.active {
  color: var(--chapter-color);
  background: color-mix(in srgb, var(--chapter-color) 9%, transparent);
  font-weight: 700;
}
.chapter-no {
  font-family: var(--font-mono);
  font-size: 0.67rem;
  opacity: 0.72;
}
.chapter-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.82rem;
}
.chapter-total {
  font-family: var(--font-mono);
  font-size: 0.66rem;
  color: var(--text-faint);
}
.chapter-chevron { transition: transform 0.2s; }
.chapter-row[aria-expanded="true"] .chapter-chevron { transform: rotate(90deg); }
.nav-docs {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.2rem 0 0.55rem 1.85rem;
  max-height: min(38vh, 340px);
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}
.nav-doc {
  width: 100%;
  display: grid;
  grid-template-columns: 31px minmax(0, 1fr);
  align-items: start;
  gap: 0.42rem;
  padding: 0.48rem 0.55rem;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--text-dim);
  text-align: left;
  transition: background 0.18s, color 0.18s;
}
.nav-doc:hover { background: rgba(255, 255, 255, 0.86); color: var(--text); }
.nav-doc.active {
  color: var(--lake);
  background: #fff;
  font-weight: 700;
  box-shadow: 0 2px 10px rgba(16, 28, 44, 0.06);
}
.nav-doc-id {
  font-family: var(--font-mono);
  font-size: 0.62rem;
  color: var(--text-faint);
}
.nav-doc.active .nav-doc-id { color: var(--lake); }
.nav-doc-title {
  min-width: 0;
  font-size: 0.76rem;
  line-height: 1.42;
}

.explorer-main {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
}
.doc-toolbar {
  height: 48px;
  flex: 0 0 48px;
  display: flex;
  align-items: center;
  padding: 0 1.8rem;
  border-bottom: 1px solid var(--line);
}
.toolbar-crumb {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.42rem;
  min-width: 0;
  color: var(--text-faint);
  font-size: 0.75rem;
}
.toolbar-crumb button {
  border: 0;
  background: transparent;
  color: var(--text-faint);
  padding: 0;
}
.toolbar-crumb button:hover { color: var(--accent); }
.toolbar-crumb strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text);
  font-weight: 600;
}
.doc-scroll {
  min-height: 0;
  overflow-y: auto;
  padding: 2.4rem clamp(1.5rem, 5vw, 5rem) 5rem;
  scroll-behavior: smooth;
}
.doc-article {
  max-width: 820px;
  margin: 0 auto;
  font-size: 0.96rem;
  line-height: 1.85;
}
.doc-article :deep(h1) {
  font-size: clamp(1.8rem, 3vw, 2.45rem);
  margin: 0 0 1.4rem;
}
.doc-article :deep(h2) {
  margin-top: 2.2rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--line);
}
.doc-article :deep(p) { margin: 0.75rem 0; }
.doc-article :deep(li) { margin: 0.45rem 0; }

.explorer-rail {
  min-width: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--line);
  background: rgba(247, 248, 250, 0.6);
}
.rail-head {
  height: 48px;
  flex: 0 0 48px;
  display: flex;
  align-items: center;
  padding: 0 1rem;
  border-bottom: 1px solid var(--line);
  color: var(--text-dim);
  font-size: 0.77rem;
  font-weight: 700;
}
.rail-scroll {
  min-height: 0;
  overflow-y: auto;
  padding: 0.7rem 0.65rem;
}
.rail-item {
  width: 100%;
  display: block;
  padding: 0.55rem 0.65rem;
  border: 0;
  border-left: 2px solid transparent;
  border-radius: 7px;
  background: transparent;
  color: var(--text-faint);
  text-align: left;
  font-size: 0.75rem;
  line-height: 1.45;
  transition: color 0.18s, background 0.18s;
}
.rail-item:hover { color: var(--text); background: rgba(255, 255, 255, 0.75); }
.rail-item.active {
  color: var(--chapter-color);
  background: #fff;
  font-weight: 700;
  box-shadow: 0 2px 10px rgba(16, 28, 44, 0.05);
}

.doc-loading { max-width: 820px; margin: 0 auto; display: flex; flex-direction: column; gap: 0.75rem; }
.loading-line {
  width: 72%;
  height: 13px;
  border-radius: 7px;
  background: linear-gradient(90deg, var(--bg-soft) 25%, var(--bg-strong) 50%, var(--bg-soft) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
.loading-line.wide { width: 48%; height: 34px; margin-bottom: 0.8rem; }
.loading-line.short { width: 46%; }
@keyframes shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}
.doc-error {
  max-width: 820px;
  margin: 0 auto;
  padding: 0.9rem 1rem;
  border: 1px solid rgba(185, 28, 28, 0.25);
  border-radius: 8px;
  background: rgba(185, 28, 28, 0.06);
  color: #b91c1c;
  font-size: 0.86rem;
}
.doc-empty {
  min-height: 50vh;
  display: grid;
  place-items: center;
  color: var(--text-faint);
  font-size: 0.86rem;
}

.explorer-enter-active,
.explorer-leave-active { transition: opacity 0.24s var(--ease-out); }
.explorer-enter-active .explorer-layout,
.explorer-leave-active .explorer-layout { transition: transform 0.3s var(--ease-out); }
.explorer-enter-from,
.explorer-leave-to { opacity: 0; }
.explorer-enter-from .explorer-layout,
.explorer-leave-to .explorer-layout { transform: translateY(10px); }

@media (max-width: 1080px) {
  .explorer-layout { grid-template-columns: 250px minmax(0, 1fr); }
  .explorer-rail { display: none; }
}

@media (max-width: 720px) {
  .explorer-head {
    grid-template-columns: 1fr auto;
    height: 58px;
    flex-basis: 58px;
    padding: 0 0.75rem;
  }
  .head-crumb { display: none; }
  .brand-mark { width: 28px; height: 28px; }
  .explorer-brand { font-size: 0.9rem; }
  .explorer-layout {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(220px, 38vh) minmax(0, 1fr);
  }
  .explorer-nav { border-right: 0; border-bottom: 1px solid var(--line); }
  .nav-scroll { padding-bottom: 0.4rem; }
  .nav-docs { max-height: 158px; }
  .doc-toolbar { padding: 0 1rem; }
  .doc-scroll { padding: 1.4rem 1rem 3rem; }
  .doc-article :deep(h1) { font-size: 1.65rem; }
}
</style>
