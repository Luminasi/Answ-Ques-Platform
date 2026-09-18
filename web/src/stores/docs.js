import { defineStore } from 'pinia'
import { request } from '../api/request'
import { API } from '../config'
import domainData from '../assets/domainData.json'

// 领域元信息：中文名 + 专属色（700 档，白底下小字均过 WCAG AA 对比度）
export const DOMAIN_META = {
  'Object-Oriented Programming': { zh: '面向对象编程', color: '#b45309', desc: '类、对象、继承与多态' },
  'Control Flow Structures': { zh: '控制流结构', color: '#0369a1', desc: '条件分支与循环逻辑' },
  'Strings and Common Data Structures': { zh: '字符串与数据结构', color: '#047857', desc: '列表、字典、元组与集合' },
  'Functions': { zh: '函数', color: '#be123c', desc: '定义、参数与作用域' },
  'Python Fundamental Syntax': { zh: '基础语法', color: '#6d28d9', desc: '变量、类型与运算符' },
  'File Operations': { zh: '文件操作', color: '#a16207', desc: '读写、路径与上下文管理' },
  'Python Development Environment': { zh: '开发环境', color: '#15803d', desc: '解释器、IDE 与虚拟环境' },
  'Exception Handling': { zh: '异常处理', color: '#b91c1c', desc: 'try-except 与自定义异常' },
  'Introduction to Python': { zh: 'Python 简介', color: '#0e7490', desc: '语言特性与发展历程' },
  'Modules': { zh: '模块', color: '#7e22ce', desc: '导入、包管理与标准库' },
}

export const useDocsStore = defineStore('docs', {
  state: () => ({
    files: [],               // 全部文档文件名 ['q001.md', ...]
    idToDomain: domainData.idToDomain,   // { 1: 'Introduction to Python', ... }
    domainIds: domainData.domainIds,     // { 'OOP': [id, ...], ... }
    activeDomain: null,      // 当前展开的领域 key
    listOpen: false,         // 文档列表抽屉是否从右侧滑入
    currentDoc: null,        // { source, title, content, chunks? } 正在阅读的文档
    docLoading: false,
    docError: '',
    readerOpen: false,
    activeChunkIndex: null, // 当前打开/高亮的 chunk，1-based；null = 未指定
    pendingChunkIndex: null,
    page: 1,
    pageSize: 24,
  }),

  getters: {
    domains() {
      return Object.keys(this.domainIds).map((key) => {
        const ids = this.domainIds[key]
        const meta = DOMAIN_META[key] || { zh: key, color: '#94a3b8', desc: '' }
        // 代表问题：取该领域第一篇文档的标题来源（id -> qNNN.md 标题在打开时才知道，这里先用文件名）
        return { key, ids, count: ids.length, ...meta }
      })
    },
    // 当前领域的文档（分页）
    activeDocs() {
      if (!this.activeDomain) return []
      const ids = this.domainIds[this.activeDomain] || []
      const start = (this.page - 1) * this.pageSize
      return ids.slice(start, start + this.pageSize).map((id) => ({
        id,
        source: `q${String(id).padStart(3, '0')}.md`,
      }))
    },
    activeTotal() {
      return this.activeDomain ? (this.domainIds[this.activeDomain] || []).length : 0
    },
    totalPages() {
      return Math.max(1, Math.ceil(this.activeTotal / this.pageSize))
    },
  },

  actions: {
    async fetchDocsList() {
      try {
        const data = await request(API.docsList())
        this.files = data.files || []
      } catch (e) {
        console.error('文档列表加载失败', e)
      }
    },

    openDomain(key) {
      this.activeDomain = key
      this.page = 1
      this.listOpen = true
    },

    closeList() {
      this.listOpen = false
    },

    setPage(p) {
      this.page = Math.max(1, Math.min(this.totalPages, p))
    },

    async openDoc(source, chunkIndex = null) {
      this.docLoading = true
      this.docError = ''
      this.readerOpen = true
      this.currentDoc = null
      this.activeChunkIndex = chunkIndex
      this.pendingChunkIndex = chunkIndex
      try {
        const data = await request(API.doc(source))
        this.currentDoc = data
        await this.loadChunks(source, chunkIndex)
      } catch (e) {
        this.docError = e.message
        this.activeChunkIndex = null
        this.pendingChunkIndex = null
      } finally {
        this.docLoading = false
      }
    },

    async loadChunks(source, chunkIndex = null) {
      if (!this.currentDoc || this.currentDoc.source !== source) return
      try {
        const data = await request(API.chunks(source))
        this.currentDoc.chunks = data.chunks || []
        const target = chunkIndex ?? this.pendingChunkIndex
        this.activeChunkIndex = target != null ? target : null
      } catch (e) {
        // 接口异常时降级为普通全文阅读，不阻塞阅读器
        this.currentDoc.chunks = []
        this.activeChunkIndex = null
        if (e.status !== 404) console.warn('chunks 接口异常', e)
      }
    },

    jumpToChunk(source, chunkIndex = null) {
      this.readerOpen = true
      if (this.currentDoc?.source === source) {
        this.pendingChunkIndex = chunkIndex
        this.activeChunkIndex = chunkIndex
        // chunks 曾加载失败时，同文档再点击可重试一次，保证能继续定位。
        if (!this.docLoading && !this.currentDoc.chunks?.length) {
          this.loadChunks(source, chunkIndex)
        }
        return
      }
      this.openDoc(source, chunkIndex)
    },

    closeReader() {
      this.readerOpen = false
      this.activeChunkIndex = null
      this.pendingChunkIndex = null
    },

    domainOfSource(source) {
      // q001.md -> 1 -> domain key
      const m = /q(\d+)\.md/.exec(source)
      if (!m) return null
      return this.idToDomain[parseInt(m[1], 10)] || null
    },
  },
})
