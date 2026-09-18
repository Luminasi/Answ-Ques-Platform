<script setup>
import { computed } from 'vue'
import { useDocsStore, DOMAIN_META } from '../../stores/docs'
import { renderMarkdown } from '../../api/markdown'

const docs = useDocsStore()

const html = computed(() => (docs.currentDoc ? renderMarkdown(docs.currentDoc.content) : ''))
const domainZh = computed(() => {
  if (!docs.currentDoc) return ''
  const key = docs.domainOfSource(docs.currentDoc.source)
  return key ? (DOMAIN_META[key]?.zh || key) : ''
})
</script>

<template>
  <Transition name="fade">
    <div v-if="docs.readerOpen" class="reader-mask" @click.self="docs.closeReader()">
      <article class="reader glass">
        <header class="reader-head">
          <div class="crumbs">
            <span v-if="domainZh" class="crumb-domain">{{ domainZh }}</span>
            <span v-if="domainZh" class="crumb-sep">/</span>
            <span class="crumb-doc">{{ docs.currentDoc?.title || docs.currentDoc?.source || '加载中' }}</span>
          </div>
          <button class="close-btn" @click="docs.closeReader()" aria-label="关闭阅读器">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
          </button>
        </header>

        <div class="reader-body" data-scrollable>
          <div v-if="docs.docLoading" class="reader-loading">
            <span class="loading-bar"></span>
            <span class="loading-bar"></span>
            <span class="loading-bar short"></span>
          </div>
          <div v-else-if="docs.docError" class="reader-error">{{ docs.docError }}</div>
          <div v-else-if="docs.currentDoc" class="md reader-md" v-html="html"></div>
        </div>
      </article>
    </div>
  </Transition>
</template>

<style scoped>
.reader-mask {
  position: absolute;
  inset: 0;
  z-index: 50;
  background: rgba(30, 41, 59, 0.3);
  backdrop-filter: blur(4px);
  display: grid;
  place-items: center;
  padding: 1.2rem;
}
.reader {
  width: min(780px, 100%);
  max-height: 100%;
  border-radius: var(--radius-card);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.reader-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.3rem;
  border-bottom: 1px solid var(--line);
}
.crumbs { display: flex; align-items: center; gap: 0.5rem; min-width: 0; font-size: 0.85rem; }
.crumb-domain { color: var(--accent); font-weight: 600; }
.crumb-sep { color: var(--text-faint); }
.crumb-doc {
  color: var(--text);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.close-btn {
  width: 30px; height: 30px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: var(--bg-soft);
  color: var(--text-dim);
  display: grid;
  place-items: center;
  transition: all 0.2s;
}
.close-btn:hover { color: var(--text); background: var(--bg-strong); }

.reader-body {
  overflow-y: auto;
  padding: 1.4rem 1.6rem 2.2rem;
  min-height: 200px;
}
.reader-md :deep(h1:first-child) { margin-top: 0; }

.reader-loading { display: flex; flex-direction: column; gap: 0.8rem; padding-top: 0.5rem; }
.loading-bar {
  height: 14px;
  border-radius: 7px;
  background: linear-gradient(90deg, var(--bg-soft) 25%, var(--bg-strong) 50%, var(--bg-soft) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
.loading-bar.short { width: 55%; }
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }

.reader-error {
  padding: 1rem 1.2rem;
  border-radius: 10px;
  background: rgba(220, 38, 38, 0.07);
  border: 1px solid rgba(220, 38, 38, 0.28);
  color: #b91c1c;
  font-size: 0.88rem;
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.3s var(--ease-out); }
.fade-enter-active .reader, .fade-leave-active .reader { transition: transform 0.35s var(--ease-out), opacity 0.3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.fade-enter-from .reader, .fade-leave-to .reader { transform: translateY(18px) scale(0.98); }
</style>
