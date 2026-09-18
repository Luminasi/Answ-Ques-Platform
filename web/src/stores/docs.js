import { defineStore } from 'pinia'
import { request } from '../api/request'
import { API } from '../config'
import domainData from '../assets/domainData.json'

// 领域元信息：中文名 + 专属色（浅色主题下取 600 档保证白底可读）
export const DOMAIN_META = {
  'Object-Oriented Programming': { zh: '面向对象编程', color: '#d97706', desc: '类、对象、继承与多态' },
  'Control Flow Structures': { zh: '控制流结构', color: '#0284c7', desc: '条件分支与循环逻辑' },
  'Strings and Common Data Structures': { zh: '字符串与数据结构', color: '#059669', desc: '列表、字典、元组与集合' },
  'Functions': { zh: '函数', color: '#e11d48', desc: '定义、参数与作用域' },
  'Python Fundamental Syntax': { zh: '基础语法', color: '#7c3aed', desc: '变量、类型与运算符' },
  'File Operations': { zh: '文件操作', color: '#b45309', desc: '读写、路径与上下文管理' },
  'Python Development Environment': { zh: '开发环境', color: '#16a34a', desc: '解释器、IDE 与虚拟环境' },
  'Exception Handling': { zh: '异常处理', color: '#dc2626', desc: 'try-except 与自定义异常' },
  'Introduction to Python': { zh: 'Python 简介', color: '#0891b2', desc: '语言特性与发展历程' },
  'Modules': { zh: '模块', color: '#9333ea', desc: '导入、包管理与标准库' },
}

export const useDocsStore = defineStore('docs', {
  state: () => ({
    files: [],               // 全部文档文件名 ['q001.md', ...]
    idToDomain: domainData.idToDomain,   // { 1: 'Introduction to Python', ... }
    domainIds: domainData.domainIds,     // { 'OOP': [id, ...], ... }
    activeDomain: null,      // 当前展开的领域 key
    listOpen: false,         // 文档列表抽屉是否从右侧滑入
    currentDoc: null,        // { source, title, content } 正在阅读的文档
    docLoading: false,
    docError: '',
    readerOpen: false,
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

    async openDoc(source) {
      this.docLoading = true
      this.docError = ''
      this.readerOpen = true
      this.currentDoc = null
      try {
        const data = await request(API.doc(source))
        this.currentDoc = data
        // 预留接口：尝试 chunk 定位，404 静默降级
        this.tryLocateChunks(source)
      } catch (e) {
        this.docError = e.message
      } finally {
        this.docLoading = false
      }
    },

    async tryLocateChunks(source) {
      try {
        const data = await request(API.chunks(source))
        if (this.currentDoc) this.currentDoc.chunks = data.chunks || []
      } catch (e) {
        // 404 接口尚未实现：静默降级，不弹窗
        if (e.status !== 404) console.warn('chunks 接口异常', e)
      }
    },

    closeReader() {
      this.readerOpen = false
    },

    domainOfSource(source) {
      // q001.md -> 1 -> domain key
      const m = /q(\d+)\.md/.exec(source)
      if (!m) return null
      return this.idToDomain[parseInt(m[1], 10)] || null
    },
  },
})
