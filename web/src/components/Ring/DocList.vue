<script setup>
import { computed } from 'vue'
import { useDocsStore, DOMAIN_META } from '../../stores/docs'

const docs = useDocsStore()

const meta = computed(() => DOMAIN_META[docs.activeDomain] || { zh: docs.activeDomain, color: '#94a3b8' })

function openDoc(source) {
  docs.openDoc(source)
}
</script>

<template>
  <Transition name="slide">
    <aside v-if="docs.listOpen" class="doc-list glass">
      <header class="list-head">
        <div>
          <h3 class="list-title" :style="{ color: meta.color }">{{ meta.zh }}</h3>
          <p class="list-sub">{{ docs.activeTotal }} 篇问答文档</p>
        </div>
        <button class="close-btn" @click="docs.closeList()" aria-label="关闭列表">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
        </button>
      </header>

      <div class="list-body" data-scrollable>
        <button
          v-for="d in docs.activeDocs"
          :key="d.source"
          class="doc-item"
          @click="openDoc(d.source)"
        >
          <span class="doc-id">{{ d.source.replace('.md', '') }}</span>
          <span class="doc-hint">点击查看全文</span>
        </button>
        <div v-if="!docs.activeDocs.length" class="list-empty">该领域暂无文档</div>
      </div>

      <footer v-if="docs.totalPages > 1" class="list-pager">
        <button class="pager-btn" :disabled="docs.page <= 1" @click="docs.setPage(docs.page - 1)">上一页</button>
        <span class="pager-info">{{ docs.page }} / {{ docs.totalPages }}</span>
        <button class="pager-btn" :disabled="docs.page >= docs.totalPages" @click="docs.setPage(docs.page + 1)">下一页</button>
      </footer>
    </aside>
  </Transition>
</template>

<style scoped>
.doc-list {
  position: absolute;
  top: 5.2rem;
  right: 1.4rem;
  bottom: 1.4rem;
  width: min(380px, calc(100vw - 2.8rem));
  border-radius: var(--radius-card);
  z-index: 40;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.list-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 1.15rem 1.2rem 0.95rem;
  border-bottom: 1px solid var(--line);
}
.list-title { font-family: var(--font-display); font-size: 1.15rem; font-weight: 700; }
.list-sub { font-size: 0.78rem; color: var(--text-faint); margin-top: 0.15rem; }
.close-btn {
  width: 30px; height: 30px;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: var(--bg-soft);
  color: var(--text-dim);
  display: grid;
  place-items: center;
  transition: all 0.2s;
}
.close-btn:hover { color: var(--text); background: var(--bg-strong); }

.list-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.8rem;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.55rem;
  align-content: start;
}
.doc-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.2rem;
  padding: 0.75rem 0.85rem;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: var(--bg-soft);
  color: var(--text);
  text-align: left;
  transition: all 0.2s var(--ease-out);
}
.doc-item:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
  transform: translateY(-2px);
}
.doc-id { font-family: var(--font-mono); font-weight: 700; font-size: 0.88rem; }
.doc-hint { font-size: 0.68rem; color: var(--text-faint); }
.list-empty { grid-column: 1 / -1; text-align: center; color: var(--text-faint); padding: 2rem; font-size: 0.85rem; }

.list-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 0.75rem;
  border-top: 1px solid var(--line);
}
.pager-btn {
  padding: 0.35rem 0.95rem;
  border-radius: var(--radius-pill);
  border: 1px solid var(--line);
  background: var(--bg-soft);
  color: var(--text-dim);
  font-size: 0.78rem;
  transition: all 0.2s;
}
.pager-btn:hover:not(:disabled) { color: var(--text); border-color: var(--line-strong); }
.pager-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.pager-info { font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-faint); }

.slide-enter-active, .slide-leave-active { transition: transform 0.4s var(--ease-out), opacity 0.4s var(--ease-out); }
.slide-enter-from, .slide-leave-to { transform: translateX(40px); opacity: 0; }
</style>
