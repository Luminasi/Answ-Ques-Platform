<script setup>
import { useDocsStore } from '../stores/docs'
import CylinderRing from '../components/Ring/CylinderRing.vue'
import DocList from '../components/Ring/DocList.vue'
import DocReader from '../components/Ring/DocReader.vue'
// 背景图备用：恢复时取消模板中 bg-img 注释即可
// import meadowClouds from '../assets/bg/meadow-clouds.jpg'

const docs = useDocsStore()

function onSelect(domain) {
  docs.openDomain(domain.key)
}
</script>

<template>
  <section class="ring-screen">
    <!-- 背景：纯白（草原云海图片备用，取消下行注释恢复） -->
    <div class="bg-scene" aria-hidden="true">
      <!-- <img class="bg-img" :src="meadowClouds" alt="" /> -->
      <!-- 深色遮罩随图片背景备用，白底下关闭 -->
      <!-- <div class="bg-scrim"></div> -->
    </div>

    <!-- 顶部标题 -->
    <header class="ring-head">
      <h2 class="ring-title">课程知识图谱</h2>
      <p class="ring-sub">拖动圆环，探索 10 个 Python 知识领域 · 共 534 篇答疑文档</p>
    </header>

    <!-- 3D 产品环 -->
    <CylinderRing :domains="docs.domains" @select="onSelect" />

    <!-- 右侧滑入的文档列表 -->
    <DocList />

    <!-- 全文阅读器 -->
    <DocReader />
  </section>
</template>

<style scoped>
.ring-screen {
  height: 100%;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.bg-scene { position: absolute; inset: 0; z-index: -1; overflow: hidden; background: #fff; }
.bg-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 20%;
}
.bg-scrim {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(to bottom, rgba(12, 20, 32, 0.42) 0%, rgba(12, 20, 32, 0.18) 40%, rgba(12, 20, 32, 0.62) 100%),
    radial-gradient(100% 70% at 50% 45%, transparent 35%, rgba(12, 20, 32, 0.35));
}

.ring-head {
  text-align: center;
  padding: clamp(1.6rem, 4vh, 3rem) 1rem 0;
  flex-shrink: 0;
  pointer-events: none;
  position: relative;
  z-index: 5;
}
.ring-title {
  font-family: var(--font-display);
  font-size: clamp(1.6rem, 3.6vw, 2.5rem);
  font-weight: 700;
  letter-spacing: -0.02em;
}
.ring-sub {
  margin-top: 0.5rem;
  color: var(--text-dim);
  font-size: clamp(0.82rem, 1.3vw, 0.95rem);
}
</style>
