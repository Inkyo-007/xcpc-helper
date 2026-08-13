<script setup lang="ts">
/** 全屏同步遮罩：首次绑定与手动同步期间弹出，背景被半透明模糊层
 * 覆盖而不可操作。
 * 指示器呼应「训练热力图」——一组迷你格子按对角线错峰点亮，
 * 形成扫描波动，代替常规转圈。 */

defineProps<{
  show: boolean
}>()

const COLS = 7
const ROWS = 3

/** 每格的动画错峰延迟（秒）：按 行 + 列 对角线推进 */
const delays = Array.from({ length: COLS * ROWS }, (_, i) => {
  const row = Math.floor(i / COLS)
  const col = i % COLS
  return (row + col) * 0.08
})
</script>

<template>
  <Teleport to="body">
    <Transition name="sync-overlay">
      <div v-if="show" class="sync-overlay" role="alert" aria-busy="true">
        <div class="overlay-card">
          <div class="mini-heat" aria-hidden="true">
            <i
              v-for="(delay, i) in delays"
              :key="i"
              class="heat-cell"
              :style="{ animationDelay: `${delay}s` }"
            />
          </div>
          <div class="overlay-label">
            正在同步训练数据<span class="dot">.</span><span class="dot">.</span
            ><span class="dot">.</span>
          </div>
          <div class="overlay-sweep" aria-hidden="true" />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.sync-overlay {
  position: fixed;
  inset: 0;
  z-index: 4000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(246 245 242 / 0.6);
  backdrop-filter: blur(6px) saturate(0.9);
  -webkit-backdrop-filter: blur(6px) saturate(0.9);
}

[data-theme='dark'] .sync-overlay {
  background: rgb(25 24 22 / 0.6);
}

.overlay-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 26px 34px 24px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  box-shadow: var(--shadow-pop);
  overflow: hidden;
}

.mini-heat {
  display: grid;
  grid-template-columns: repeat(7, 15px);
  gap: 4px;
}

.heat-cell {
  width: 15px;
  height: 15px;
  border-radius: 4px;
  background: var(--surface-2);
  animation: cell-wave 1.5s ease-in-out infinite;
}

@keyframes cell-wave {
  0%,
  100% {
    background: var(--surface-2);
    transform: scale(1);
  }
  30% {
    background: var(--accent);
    transform: scale(1.12);
  }
}

.overlay-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  letter-spacing: 0.02em;
}

.dot {
  display: inline-block;
  color: var(--accent-strong);
  animation: dot-blink 1.5s ease-in-out infinite;
}

.dot:nth-of-type(2) {
  animation-delay: 0.2s;
}

.dot:nth-of-type(3) {
  animation-delay: 0.4s;
}

@keyframes dot-blink {
  0%,
  100% {
    opacity: 0.15;
  }
  30% {
    opacity: 1;
  }
}

/* 卡片底部的 accent 扫光条 */
.overlay-sweep {
  width: 100%;
  height: 2px;
  border-radius: 99px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    var(--accent) 50%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: sweep 1.5s linear infinite;
}

@keyframes sweep {
  from {
    background-position: 100% 0;
  }
  to {
    background-position: -100% 0;
  }
}

/* 遮罩淡入淡出，卡片轻微上浮 */
.sync-overlay-enter-active,
.sync-overlay-leave-active {
  transition: opacity 0.22s ease;
}

.sync-overlay-enter-active .overlay-card,
.sync-overlay-leave-active .overlay-card {
  transition: transform 0.22s cubic-bezier(0.22, 0.8, 0.3, 1.1), opacity 0.22s ease;
}

.sync-overlay-enter-from,
.sync-overlay-leave-to {
  opacity: 0;
}

.sync-overlay-enter-from .overlay-card,
.sync-overlay-leave-to .overlay-card {
  transform: translateY(8px) scale(0.97);
  opacity: 0;
}
</style>
