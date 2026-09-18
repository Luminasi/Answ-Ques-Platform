<script setup>
import { useNotesStore } from '../../stores/notes'

const notes = useNotesStore()
</script>

<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="notes.drawerOpen" class="drawer-mask" @click.self="notes.toggleDrawer(false)">
        <aside class="drawer glass">
          <header class="drawer-head">
            <h3>学习笔记</h3>
            <div class="drawer-actions">
              <button v-if="notes.notes.length" class="action" @click="notes.exportMarkdown()">导出 Markdown</button>
              <button class="action close" @click="notes.toggleDrawer(false)">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
              </button>
            </div>
          </header>

          <div class="drawer-body" data-scrollable>
            <div v-if="!notes.notes.length" class="notes-empty">
              <svg width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" opacity="0.35"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
              <p>还没有笔记</p>
              <p class="hint">在回答下方点击「存笔记」即可收藏</p>
            </div>
            <article v-for="n in notes.notes" :key="n.id" class="note-card">
              <div class="note-q">{{ n.question || '（未记录问题）' }}</div>
              <div class="note-a">{{ (n.answer || '').slice(0, 180) }}{{ (n.answer || '').length > 180 ? '…' : '' }}</div>
              <div class="note-meta">
                <span>{{ n.time }}</span>
                <span v-if="n.source" class="note-src">{{ n.source }}</span>
                <button class="note-del" @click="notes.remove(n.id)">删除</button>
              </div>
            </article>
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.drawer-mask {
  position: fixed;
  inset: 0;
  z-index: 120;
  background: rgba(30, 41, 59, 0.28);
  backdrop-filter: blur(3px);
}
.drawer {
  position: absolute;
  top: 1rem;
  right: 1rem;
  bottom: 1rem;
  width: min(400px, calc(100vw - 2rem));
  border-radius: var(--radius-card);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.1rem 1.2rem 0.9rem;
  border-bottom: 1px solid var(--line);
}
.drawer-head h3 { font-family: var(--font-display); font-size: 1.05rem; }
.drawer-actions { display: flex; align-items: center; gap: 0.5rem; }
.action {
  border: 1px solid var(--line);
  background: var(--bg-soft);
  color: var(--text-dim);
  border-radius: var(--radius-pill);
  padding: 0.32rem 0.85rem;
  font-size: 0.76rem;
  transition: all 0.2s;
}
.action:hover { color: var(--text); border-color: var(--line-strong); }
.action.close { padding: 0.35rem; display: grid; place-items: center; }

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1.2rem;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}
.notes-empty {
  text-align: center;
  color: var(--text-faint);
  padding: 3rem 1rem;
  font-size: 0.88rem;
}
.notes-empty .hint { font-size: 0.76rem; margin-top: 0.3rem; }

.note-card {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--bg-soft);
  padding: 0.85rem 1rem;
}
.note-q { font-weight: 600; font-size: 0.86rem; margin-bottom: 0.4rem; color: var(--accent); }
.note-a {
  font-size: 0.8rem;
  color: var(--text-dim);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.note-meta {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  margin-top: 0.55rem;
  font-size: 0.7rem;
  color: var(--text-faint);
}
.note-src { font-family: var(--font-mono); }
.note-del {
  margin-left: auto;
  border: none;
  background: none;
  color: #f87171;
  font-size: 0.72rem;
  padding: 0;
}
.note-del:hover { text-decoration: underline; }

/* 过渡动画 */
.drawer-enter-active, .drawer-leave-active { transition: opacity 0.3s var(--ease-out); }
.drawer-enter-active .drawer, .drawer-leave-active .drawer { transition: transform 0.35s var(--ease-out); }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-from .drawer, .drawer-leave-to .drawer { transform: translateX(30px); }
</style>
