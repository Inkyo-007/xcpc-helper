<script setup lang="ts">
/** 平台视图右栏同步进行态面板：进度环 + 百分比（总量可知的平台），
 * 总量未知时退化为不定态旋转弧。同步是后台属性——面板只呈现状态，
 * 用户可自由切换页签与其他功能，完成后由后台轮询自动刷新数据。 */

import { computed } from 'vue'

const props = defineProps<{
  /** 平台显示名（如 洛谷） */
  platformName: string
  /** 同步进度 0~1；null/undefined = 总量未知（不定态） */
  progress?: number | null
  /** 同步账号展示名 */
  account?: string
}>()

// 环形参数（r=52，周长 ≈ 326.73）
const R = 52
const CIRCUMFERENCE = 2 * Math.PI * R

const determinate = computed(() => props.progress != null)
const percent = computed(() => Math.min(100, Math.round((props.progress ?? 0) * 100)))
const dashOffset = computed(() => CIRCUMFERENCE * (1 - (props.progress ?? 0)))
</script>

<template>
  <div class="sync-panel">
    <div class="ring-wrap" :class="{ indeterminate: !determinate }">
      <svg viewBox="0 0 120 120" class="ring">
        <defs>
          <linearGradient id="sync-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="var(--accent)" />
            <stop offset="100%" stop-color="var(--accent-strong)" />
          </linearGradient>
        </defs>
        <circle class="ring-track" cx="60" cy="60" :r="R" />
        <circle
          class="ring-arc"
          cx="60"
          cy="60"
          :r="R"
          :stroke-dasharray="determinate ? CIRCUMFERENCE : `${CIRCUMFERENCE * 0.28} ${CIRCUMFERENCE}`"
          :stroke-dashoffset="determinate ? dashOffset : 0"
        />
      </svg>
      <div class="ring-center">
        <span v-if="determinate" class="ring-percent mono">{{ percent }}<i>%</i></span>
        <span v-else class="ring-waiting">同步中</span>
      </div>
    </div>
    <p class="sync-caption">
      正在同步 <b>{{ platformName }}</b><template v-if="account">（{{ account }}）</template>的训练数据
    </p>
    <p class="sync-hint">可自由切换到其他页面，完成后会自动刷新</p>
  </div>
</template>

<style scoped>
.sync-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 320px;
  animation: panel-in 0.3s ease both;
}

@keyframes panel-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.ring-wrap {
  position: relative;
  width: 132px;
  height: 132px;
  margin-bottom: 10px;
}

.ring {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.ring-track {
  fill: none;
  stroke: var(--surface-2);
  stroke-width: 5;
}

.ring-arc {
  fill: none;
  stroke: url(#sync-grad);
  stroke-width: 5;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.55s cubic-bezier(0.22, 0.8, 0.3, 1);
  filter: drop-shadow(0 0 6px var(--accent-soft));
  animation: ring-breathe 2.4s ease-in-out infinite;
}

/* 弧光呼吸：比旋转更克制的"进行中"表达 */
@keyframes ring-breathe {
  0%,
  100% {
    filter: drop-shadow(0 0 3px var(--accent-soft));
  }
  50% {
    filter: drop-shadow(0 0 9px var(--accent));
  }
}

/* 不定态：短弧持续旋转 */
.indeterminate .ring-arc {
  animation: ring-spin 1.6s linear infinite;
  transition: none;
}

@keyframes ring-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.indeterminate .ring {
  transform: rotate(-90deg);
}

.indeterminate .ring-arc {
  transform-origin: 60px 60px;
}

.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ring-percent {
  font-size: 26px;
  font-weight: 700;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.ring-percent i {
  font-style: normal;
  font-size: 13px;
  color: var(--muted);
  margin-left: 2px;
}

.ring-waiting {
  font-size: 15px;
  font-weight: 600;
  color: var(--muted);
  letter-spacing: 0.05em;
}

.sync-caption {
  margin: 0;
  font-size: 13px;
  color: var(--text);
}

.sync-caption b {
  color: var(--accent-strong);
}

.sync-hint {
  margin: 0;
  font-size: 11.5px;
  color: var(--faint);
}
</style>
