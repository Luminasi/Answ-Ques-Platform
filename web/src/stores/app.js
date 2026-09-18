import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    currentScreen: 0, // 0 = 对话屏, 1 = 文档环屏
    docsReady: false, // 文档服务健康
    ragReady: false,  // RAG 服务健康
  }),
  actions: {
    goTo(screen) {
      this.currentScreen = screen
    },
  },
})
