<script setup lang="ts">
/** 训练分析页：整页滚动的卡片式布局，展示四维诊断（难度分布 / 提交质量 / 训练节奏 / 薄弱点）。
 *  数据来自后端 /activity/analysis（当前用户组，切组自动刷新），AI 报告属下一阶段。
 */

import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ChartNoAxesCombined, RefreshCw, TriangleAlert } from 'lucide-vue-next'
import { NButton, NSpin } from 'naive-ui'
import * as api from '@/features/activity/api'
import DifficultyChart from '@/features/activity/components/analysis/DifficultyChart.vue'
import RhythmChart from '@/features/activity/components/analysis/RhythmChart.vue'
import VerdictChart from '@/features/activity/components/analysis/VerdictChart.vue'
import WeakPoints from '@/features/activity/components/analysis/WeakPoints.vue'
import { useUserGroups } from '@/features/activity/profile'
import type { AnalysisData } from '@/features/activity/types'

const router = useRouter()
const { currentKey, ensureLoaded } = useUserGroups()

const data = ref<AnalysisData | null>(null)
const loading = ref(false)
const failed = ref(false)

let req = 0
async function refresh(): Promise<void> {
  const id = ++req
  loading.value = true
  failed.value = false
  try {
    const res = await api.fetchAnalysis()
    if (id === req) data.value = res
  } catch {
    if (id === req) failed.value = true
  } finally {
    if (id === req) loading.value = false
  }
}

const hasData = computed(() => {
  const d = data.value
  return (
    !!d &&
    (d.difficulty.length > 0 ||
      d.verdicts.length > 0 ||
      d.rhythm.weeks.length > 0 ||
      d.weakPoints.length > 0)
  )
})

watch(currentKey, () => void refresh())

onMounted(async () => {
  await ensureLoaded()
  await refresh()
})
</script>

<template>
  <div class="an-page">
    <header class="an-head">
      <div class="an-title">
        <h1>训练分析</h1>
        <p>基于本地同步数据聚合生成；难度按 rating 分档为近似值（跨平台尺度存在差异），薄弱点与技能树同口径。</p>
      </div>
      <NButton quaternary size="small" :loading="loading" @click="refresh">
        <template #icon><RefreshCw :size="14" /></template>
        刷新
      </NButton>
    </header>

    <section v-if="loading" class="card an-center">
      <NSpin size="large" />
    </section>

    <section v-else-if="failed" class="card an-center">
      <div class="an-state-icon">
        <TriangleAlert :size="26" />
      </div>
      <h2 class="an-state-title">训练分析加载失败</h2>
      <p class="an-hint">请确认后端服务已启动、账号已绑定并完成同步，然后重试。</p>
      <NButton size="small" @click="refresh">
        <template #icon><RefreshCw :size="14" /></template>
        重试
      </NButton>
    </section>

    <section v-else-if="!hasData" class="card an-center">
      <div class="an-state-icon">
        <ChartNoAxesCombined :size="26" />
      </div>
      <h2 class="an-state-title">还没有可分析的训练数据</h2>
      <p class="an-hint">绑定竞赛平台账号并同步做题记录后，这里会生成多维诊断。</p>
      <NButton type="primary" @click="router.push('/activity/overview')">去绑定账号</NButton>
    </section>

    <template v-else>
      <div class="an-grid">
        <section class="card an-card">
          <header class="an-card-head">
            <span class="card-title">难度分布</span>
          </header>
          <DifficultyChart :bands="data!.difficulty" />
        </section>

        <section class="card an-card">
          <header class="an-card-head">
            <span class="card-title">提交质量</span>
          </header>
          <VerdictChart :verdicts="data!.verdicts" />
        </section>
      </div>

      <section class="card an-card">
        <header class="an-card-head">
          <span class="card-title">训练节奏</span>
        </header>
        <RhythmChart :rhythm="data!.rhythm" />
      </section>

      <section class="card an-card">
        <header class="an-card-head">
          <span class="card-title">薄弱点</span>
        </header>
        <WeakPoints :weak-points="data!.weakPoints" />
      </section>
    </template>
  </div>
</template>

<style scoped>
.an-page {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 20px 16px;
}

.an-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex: none;
}

.an-title h1 {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 700;
}

.an-title p {
  margin: 0;
  font-size: 13px;
  color: var(--faint);
}

.an-center {
  flex: 1;
  min-height: 360px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-align: center;
}

.an-state-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--faint);
}

.an-state-title {
  margin: 6px 0 0;
  font-size: 16px;
  font-weight: 600;
}

.an-hint {
  margin: 0 0 4px;
  font-size: 13px;
  color: var(--faint);
  max-width: 420px;
}

.an-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.an-card {
  padding: 12px 16px 14px;
  flex: none;
}

.an-card-head {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

@media (max-width: 900px) {
  .an-grid {
    grid-template-columns: 1fr;
  }
}
</style>
