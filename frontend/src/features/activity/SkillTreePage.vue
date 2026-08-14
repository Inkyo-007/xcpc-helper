<script setup lang="ts">
/** 技能树页：整页展示算法技能树（根 → 技能域 → 技能）。
 * 数据来自后端 /activity/skill-tree（当前用户组，切组自动刷新）。
 * 仅 Codeforces 标签参与技能映射（AtCoder 无标签），空态引导去绑定 CF。
 */

import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ChartNoAxesCombined, RefreshCw, TriangleAlert } from 'lucide-vue-next'
import { NButton, NSpin } from 'naive-ui'
import SkillTree from '@/features/activity/components/SkillTree.vue'
import * as api from '@/features/activity/api'
import { useUserGroups } from '@/features/activity/profile'
import type { SkillTreeData } from '@/features/activity/types'

const router = useRouter()
const { currentKey, ensureLoaded } = useUserGroups()

const data = ref<SkillTreeData | null>(null)
const loading = ref(false)
const failed = ref(false)

let req = 0
async function refresh(): Promise<void> {
  const id = ++req
  loading.value = true
  failed.value = false
  try {
    const res = await api.fetchSkillTree()
    if (id === req) data.value = res
  } catch {
    if (id === req) failed.value = true
  } finally {
    if (id === req) loading.value = false
  }
}

const hasTree = computed(() => (data.value?.domains.length ?? 0) > 0)
const totalLabel = computed(() =>
  data.value
    ? `共掌握 ${data.value.totals.acCount} 题 · 总掌握度 ${Math.round(data.value.totals.proficiency * 100)}%`
    : '',
)

watch(currentKey, () => void refresh())

onMounted(async () => {
  await ensureLoaded()
  await refresh()
})
</script>

<template>
  <div class="st-page">
    <header class="st-head">
      <div class="st-title">
        <h1>技能树</h1>
        <p>基于 Codeforces 题目标签聚合：扇区大小反映做题量，颜色深浅反映掌握度，点击领域可下钻。</p>
      </div>
      <NButton quaternary size="small" :loading="loading" @click="refresh">
        <template #icon><RefreshCw :size="14" /></template>
        刷新
      </NButton>
    </header>

    <section v-if="loading" class="st-panel st-center">
      <NSpin size="large" />
    </section>

    <section v-else-if="failed" class="st-panel st-center">
      <div class="empty-icon">
        <TriangleAlert :size="26" />
      </div>
      <h2 class="st-empty-title">技能树加载失败</h2>
      <p class="st-hint">请确认后端服务已启动、账号已绑定并完成同步，然后重试。</p>
      <NButton size="small" @click="refresh">
        <template #icon><RefreshCw :size="14" /></template>
        重试
      </NButton>
    </section>

    <section v-else-if="!hasTree" class="st-panel st-center">
      <div class="empty-icon">
        <ChartNoAxesCombined :size="26" />
      </div>
      <h2 class="st-empty-title">还没有技能树数据</h2>
      <p class="st-hint">绑定 Codeforces 账号并同步做题记录后，这里会生成你的算法技能树。</p>
      <NButton type="primary" @click="router.push('/activity/overview')">去绑定 Codeforces</NButton>
    </section>

    <section v-else class="st-panel">
      <header class="st-meta">
        <span>{{ totalLabel }}</span>
      </header>
      <SkillTree :data="data!" />
    </section>
  </div>
</template>

<style scoped>
.st-page {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 20px 16px;
}

.st-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex: none;
}

.st-title h1 {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 700;
}

.st-title p {
  margin: 0;
  font-size: 13px;
  color: var(--faint);
}

.st-panel {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.st-center {
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-align: center;
  min-height: 360px;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--faint);
}

.st-empty-title {
  margin: 6px 0 0;
  font-size: 16px;
  font-weight: 600;
}

.st-hint {
  margin: 0 0 4px;
  font-size: 13px;
  color: var(--faint);
  max-width: 420px;
}

.st-meta {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  font-size: 12px;
  color: var(--faint);
  margin-bottom: 4px;
}
</style>
