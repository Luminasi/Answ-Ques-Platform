<script setup>
import { computed } from 'vue'
import { useAppStore } from '../stores/app'
import { useChatStore } from '../stores/chat'
import Sidebar from '../components/Chat/Sidebar.vue'
import MessageList from '../components/Chat/MessageList.vue'
import InputBox from '../components/Chat/InputBox.vue'
import NotesDrawer from '../components/Chat/NotesDrawer.vue'
import BloubPet from '../components/Chat/BloubPet.vue'
// 背景图备用：恢复时取消模板中 bg-img 注释即可
// import lakeDusk from '../assets/bg/lake-dusk.jpg'

const app = useAppStore()
const chat = useChatStore()

// 空态 = 当前会话没有消息且不在加载历史：输入框居中
const isEmpty = computed(() => chat.messages.length === 0 && !chat.loadingHistory)
</script>

<template>
  <section class="chat-screen">
    <!-- 背景：纯白（黄昏山湖图片备用，取消下行注释恢复） -->
    <div class="bg-scene" aria-hidden="true">
      <!-- <img class="bg-img" :src="lakeDusk" alt="" /> -->
      <!-- 深色遮罩随图片背景备用，白底下关闭 -->
      <!-- <div class="bg-scrim"></div> -->
    </div>

    <div class="layout">
      <Sidebar />

      <!-- 整个右侧就是对话界面，无容器卡片 -->
      <main class="chat-main">
        <!-- 顶栏 -->
        <header class="topbar">
          <div class="brand">
            <span class="brand-mark">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1a1206" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </span>
            <span class="brand-name">课程答疑平台</span>
          </div>
          <div class="status">
            <span class="status-item"><span class="dot" :class="{ on: app.docsReady }"></span>文档服务</span>
            <span class="status-item"><span class="dot" :class="{ on: app.ragReady }"></span>问答服务</span>
          </div>
        </header>

        <!-- 空态：欢迎语 + 居中输入框 -->
        <div v-if="isEmpty" class="empty-stage">
          <div class="empty-inner">
            <div class="empty-mark">
              <BloubPet :size="110" color="orange" paper="#223044" />
            </div>
            <h2 class="empty-title">你好，让我们开始聊天吧</h2>
            <p class="empty-sub">基于 534 篇 Python 课程问答语料，支持多轮上下文对话</p>
            <InputBox centered />
          </div>
        </div>

        <!-- 对话态：消息流在上，输入框沉底；内容列居中限宽但无卡片包裹 -->
        <template v-else>
          <div class="thread">
            <div class="thread-inner">
              <MessageList />
            </div>
          </div>
          <div class="composer">
            <div class="composer-inner">
              <InputBox />
            </div>
          </div>
        </template>
      </main>
    </div>

    <NotesDrawer />
  </section>
</template>

<style scoped>
.chat-screen {
  height: 100%;
  position: relative;
}

/* ---- 背景场景 ---- */
.bg-scene { position: absolute; inset: 0; z-index: -1; overflow: hidden; background: #fff; }
.bg-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 30%;
}
.bg-scrim {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(to bottom, rgba(12, 20, 32, 0.3) 0%, rgba(12, 20, 32, 0.5) 55%, rgba(12, 20, 32, 0.78) 100%),
    radial-gradient(120% 90% at 50% 0%, transparent 45%, rgba(12, 20, 32, 0.35));
}

/* ---- 整页布局：左侧栏 + 对话区铺满 ---- */
.layout {
  display: flex;
  height: 100%;
}

.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  /* 无任何卡片包裹：无背景、无边框、无圆角 */
}

/* ---- 顶栏 ---- */
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  padding: 0.9rem clamp(1.2rem, 3vw, 2.2rem) 0.6rem;
}
.brand { display: flex; align-items: center; gap: 0.6rem; }
.brand-mark {
  width: 32px; height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--accent), #fbbf24);
  display: grid;
  place-items: center;
  box-shadow: 0 4px 16px rgba(245, 158, 11, 0.35);
}
.brand-name {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 1.02rem;
  letter-spacing: 0.01em;
}
.status { display: flex; gap: 1.1rem; }
.status-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.76rem;
  color: var(--text-dim);
}

/* ---- 对话列：内容居中限宽，页面本身是容器 ---- */
.thread {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.thread-inner {
  flex: 1;
  min-height: 0;
  width: min(100% - 2.4rem, 800px);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}
.composer {
  flex-shrink: 0;
  padding: 0.4rem 0 1.2rem;
}
.composer-inner {
  width: min(100% - 2.4rem, 800px);
  margin: 0 auto;
}

/* ---- 空态：输入框居中 ---- */
.empty-stage {
  flex: 1;
  display: grid;
  place-items: center;
  min-height: 0;
  animation: empty-in 0.5s var(--ease-out);
  padding: 0 1.2rem;
}
@keyframes empty-in {
  from { opacity: 0; transform: translateY(14px); }
  to { opacity: 1; transform: none; }
}
.empty-inner {
  width: min(640px, 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.empty-mark { margin-bottom: 1.1rem; opacity: 0.9; }
.empty-title {
  font-family: var(--font-display);
  font-size: clamp(1.4rem, 3vw, 1.9rem);
  font-weight: 700;
  letter-spacing: -0.01em;
  margin-bottom: 0.55rem;
}
.empty-sub { color: var(--text-dim); font-size: 0.9rem; margin-bottom: 1.8rem; }
.empty-inner :deep(.input-wrap) { width: 100%; padding-top: 0; }

@media (max-width: 900px) {
  .layout :deep(.sidebar) { display: none; }
}
</style>
