<script setup>
import { useDocsStore } from '../../stores/docs'
import { useAppStore } from '../../stores/app'
import { mascotPanel } from '../../stores/mascot'

const props = defineProps({
  sources: { type: Array, default: () => [] }, // [{rank, source, score, snippet}]
})

const docs = useDocsStore()
const app = useAppStore()

function open(source, chunkIndex = null) {
  // 跳到第二屏并打开文档全文；从吉祥物面板点击时顺便收起面板
  mascotPanel.open = false
  app.goTo(1)
  docs.openDoc(source, chunkIndex)
}
</script>

<template>
  <div v-if="sources.length" class="sources">
    <div class="sources-title">参考来源</div>
    <div class="sources-grid">
      <button
        v-for="s in sources"
        :key="s.rank"
        class="source-card"
        @click="open(s.source, s.chunk_index)"
      >
        <span class="source-rank">#{{ s.rank }}</span>
        <span class="source-body">
          <span class="source-name">{{ s.source }}</span>
          <span class="source-snippet">{{ s.snippet }}</span>
        </span>
        <span class="source-score">{{ Number(s.score).toFixed(2) }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.sources { margin-top: 0.8rem; }
.sources-title {
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-faint);
  margin-bottom: 0.5rem;
  font-family: var(--font-display);
  font-weight: 600;
}
.sources-grid {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}
.source-card {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.6rem 0.8rem;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: var(--bg-soft);
  color: var(--text);
  text-align: left;
  transition: all 0.2s var(--ease-out);
}
.source-card:hover {
  background: var(--lake-soft);
  border-color: rgba(2, 132, 199, 0.45);
  transform: translateX(3px);
}
.source-rank {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--lake);
  font-weight: 700;
}
.source-body { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.source-name { font-size: 0.83rem; font-weight: 600; }
.source-snippet {
  font-size: 0.76rem;
  color: var(--text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-score {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: var(--text-faint);
}
</style>
