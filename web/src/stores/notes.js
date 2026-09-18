import { defineStore } from 'pinia'

const KEY = 'aqapp.notes.v1'

function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || []
  } catch {
    return []
  }
}

export const useNotesStore = defineStore('notes', {
  state: () => ({
    notes: load(), // [{id, question, answer, source, time}]
    drawerOpen: false,
  }),
  actions: {
    persist() {
      localStorage.setItem(KEY, JSON.stringify(this.notes))
    },
    add(note) {
      this.notes.unshift({
        id: Date.now(),
        time: new Date().toLocaleString('zh-CN'),
        ...note,
      })
      this.persist()
    },
    remove(id) {
      this.notes = this.notes.filter((n) => n.id !== id)
      this.persist()
    },
    clear() {
      this.notes = []
      this.persist()
    },
    toggleDrawer(open) {
      this.drawerOpen = open ?? !this.drawerOpen
    },
    exportMarkdown() {
      const lines = this.notes.map((n, i) =>
        `## 笔记 ${i + 1} · ${n.time}\n\n**问题**：${n.question || '（未记录）'}\n\n${n.answer || ''}\n\n${n.source ? `来源：${n.source}` : ''}`
      )
      const content = `# 课程答疑笔记\n\n导出于 ${new Date().toLocaleString('zh-CN')}\n\n${lines.join('\n\n---\n\n')}`
      const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `课程答疑笔记-${Date.now()}.md`
      a.click()
      URL.revokeObjectURL(url)
    },
  },
})
