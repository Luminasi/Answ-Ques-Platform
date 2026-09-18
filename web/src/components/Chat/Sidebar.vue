<script setup>
import { useChatStore } from '../../stores/chat'
import { useNotesStore } from '../../stores/notes'

const chat = useChatStore()
const notes = useNotesStore()
</script>

<template>
  <aside class="sidebar">
    <button class="btn btn-primary new-chat" @click="chat.newChat()">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
      新建会话
    </button>

    <div class="conv-list" data-scrollable>
      <button
        v-for="c in chat.conversations"
        :key="c.id"
        class="conv-item"
        :class="{ on: c.id === chat.conversationId }"
        @click="chat.selectConversation(c.id)"
      >
        <span class="conv-name">{{ c.name }}</span>
        <span class="conv-time">{{ c.updated_at.slice(5, 16) }}</span>
      </button>
      <div v-if="!chat.conversations.length" class="conv-empty">暂无会话</div>
    </div>

    <button class="notes-entry" @click="notes.toggleDrawer(true)">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
      学习笔记
      <span v-if="notes.notes.length" class="notes-count">{{ notes.notes.length }}</span>
    </button>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 250px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: 1rem 0.85rem;
  gap: 1rem;
  overflow: hidden;
  /* 贴边全高侧栏：无圆角、无外边距，用分隔线与对话区分界 */
  border-radius: 0;
  border: none;
  border-right: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}
.new-chat { width: 100%; }
.conv-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-height: 0;
}
.conv-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  padding: 0.6rem 0.75rem;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-dim);
  text-align: left;
  transition: background 0.2s, color 0.2s, border-color 0.2s;
}
.conv-item:hover { background: var(--bg-soft); color: var(--text); }
.conv-item.on {
  background: var(--accent-soft);
  border-color: rgba(217, 119, 6, 0.4);
  color: var(--text);
}
.conv-name {
  font-size: 0.88rem;
  font-weight: 500;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-time { font-size: 0.72rem; color: var(--text-faint); }
.conv-empty {
  text-align: center;
  color: var(--text-faint);
  font-size: 0.82rem;
  padding: 2rem 0;
}
.notes-entry {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.65rem 0.75rem;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: var(--bg-soft);
  color: var(--text-dim);
  font-size: 0.86rem;
  font-weight: 500;
  transition: all 0.2s;
}
.notes-entry:hover { background: var(--bg-strong); color: var(--text); }
.notes-count {
  margin-left: auto;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--accent);
  color: #1a1206;
  font-size: 0.7rem;
  font-weight: 700;
  display: grid;
  place-items: center;
}
</style>
