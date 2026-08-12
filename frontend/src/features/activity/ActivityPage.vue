<script setup lang="ts">
/** 数据总览页：左右双栏布局（无分界线）。
 * 左栏：用户信息卡 + 近期提交；右栏：统计卡片 + 训练热力图 + 通过数柱状图。 */

import { computed, onMounted, ref } from 'vue'
import { ChartColumn, MousePointerClick, Plus } from 'lucide-vue-next'
import { NButton, useMessage } from 'naive-ui'
import AccountBindModal from '@/features/activity/components/AccountBindModal.vue'
import ActivityHeatmap from '@/features/activity/components/ActivityHeatmap.vue'
import PassBarChart from '@/features/activity/components/PassBarChart.vue'
import PlatformTabs from '@/features/activity/components/PlatformTabs.vue'
import StatCards from '@/features/activity/components/StatCards.vue'
import SubmissionList from '@/features/activity/components/SubmissionList.vue'
import SyncBar from '@/features/activity/components/SyncBar.vue'
import UserProfileCard from '@/features/activity/components/UserProfileCard.vue'
import { monthlySolved, weeklySolved } from '@/features/activity/model/bars'
import { useActivity } from '@/features/activity/store'
import type { PlatformId } from '@/features/activity/types'

const {
  accounts,
  activePlatform,
  selectedDate,
  syncing,
  mergedDaily,
  totals,
  entries,
  recentEntries,
  lastSyncLabel,
  init,
  setPlatform,
  selectDate,
  syncNow,
  bindAccount,
  unbindAccount,
} = useActivity()

const message = useMessage()
const showBind = ref(false)

const weeklyBars = computed(() => weeklySolved(mergedDaily.value))
const monthlyBars = computed(() => monthlySolved(mergedDaily.value))

onMounted(init)

async function onBind(platform: PlatformId, handle: string): Promise<void> {
  await bindAccount(platform, handle)
  message.success('绑定成功，已完成首次同步')
}
</script>

<template>
  <div class="act-page">
    <div class="act-toolbar">
      <PlatformTabs
        :model-value="activePlatform"
        :accounts="accounts"
        @update:model-value="setPlatform"
      />
      <SyncBar
        :last-sync-label="lastSyncLabel"
        :syncing="syncing"
        :accounts="accounts"
        @sync="syncNow"
        @bind="showBind = true"
        @unbind="unbindAccount"
      />
    </div>

    <div v-if="accounts.length" class="act-body">
      <aside class="act-side">
        <UserProfileCard />
        <section class="act-panel act-submissions">
          <SubmissionList
            :selected-date="selectedDate"
            :recent="recentEntries"
            :day-entries="entries"
          />
        </section>
      </aside>

      <div class="act-main">
        <StatCards :totals="totals" />

        <section class="act-panel">
          <header class="panel-head">
            <span class="panel-title">训练热力</span>
            <span class="panel-hint">
              <MousePointerClick :size="12" />
              点击格子查看当日明细，再次点击取消
            </span>
            <span class="heat-legend">
              少
              <i class="legend-cell lv0"></i>
              <i class="legend-cell lv1"></i>
              <i class="legend-cell lv2"></i>
              <i class="legend-cell lv3"></i>
              <i class="legend-cell lv4"></i>
              <i class="legend-cell lv5"></i>
              多
            </span>
          </header>
          <ActivityHeatmap :daily="mergedDaily" :selected="selectedDate" @select="selectDate" />
        </section>

        <div class="act-charts">
          <section class="act-panel">
            <header class="panel-head">
              <span class="panel-title">近 7 天通过</span>
            </header>
            <PassBarChart :data="weeklyBars" />
          </section>
          <section class="act-panel">
            <header class="panel-head">
              <span class="panel-title">近 12 个月通过</span>
            </header>
            <PassBarChart :data="monthlyBars" />
          </section>
        </div>
      </div>
    </div>

    <div v-else class="act-empty">
      <div class="empty-icon">
        <ChartColumn :size="26" />
      </div>
      <h2 class="empty-title">还没有训练数据</h2>
      <p class="empty-hint">绑定一个竞赛平台账号，同步后这里会展示你的训练统计。</p>
      <NButton type="primary" @click="showBind = true">
        <template #icon><Plus :size="15" /></template>
        绑定第一个账号
      </NButton>
    </div>

    <AccountBindModal v-model:show="showBind" @bind="onBind" />
  </div>
</template>

<style scoped>
.act-page {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 20px 16px;
}

.act-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: none;
}

/* 左右双栏：仅以间距区分，不画分界线 */
.act-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr);
  gap: 16px;
}

.act-side {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.act-submissions {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.act-main {
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 4px;
}

.act-main::-webkit-scrollbar {
  width: 10px;
}

.act-main::-webkit-scrollbar-thumb {
  background: var(--accent);
  border-radius: 99px;
  border: 3px solid transparent;
  background-clip: content-box;
}

.act-charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.act-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  padding: 12px 16px 10px;
  flex: none;
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}

.panel-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  letter-spacing: 0.02em;
}

.panel-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--faint);
}

.heat-legend {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-left: auto;
  font-size: 11px;
  color: var(--faint);
}

.legend-cell {
  width: 11px;
  height: 11px;
  border-radius: 3px;
}

.legend-cell.lv0 {
  background: var(--surface-2);
  border: 1px solid var(--border);
}

.legend-cell.lv1 {
  background: hsl(var(--hue) 68% 48% / 0.16);
}

.legend-cell.lv2 {
  background: hsl(var(--hue) 68% 48% / 0.42);
}

.legend-cell.lv3 {
  background: hsl(var(--hue) 68% 48% / 0.62);
}

.legend-cell.lv4 {
  background: hsl(var(--hue) 68% 48% / 0.82);
}

.legend-cell.lv5 {
  background: hsl(var(--hue) 68% 48% / 1);
}

.act-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--faint);
  text-align: center;
  padding: 40px;
}

.empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 60px;
  height: 60px;
  margin-bottom: 6px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--accent);
}

.empty-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}

.empty-hint {
  margin: 0 0 6px;
  max-width: 340px;
  font-size: 12.5px;
}

@media (max-width: 1080px) {
  .act-page {
    overflow-y: auto;
  }

  .act-body {
    flex: none;
    grid-template-columns: 1fr;
  }

  .act-side {
    min-height: auto;
  }

  .act-submissions {
    flex: none;
    max-height: 360px;
  }

  .act-main {
    overflow: visible;
    padding-right: 0;
  }
}

@media (max-width: 900px) {
  .act-charts {
    grid-template-columns: 1fr;
  }
}

.act-page::-webkit-scrollbar {
  width: 10px;
}

.act-page::-webkit-scrollbar-thumb {
  background: var(--accent);
  border-radius: 99px;
  border: 3px solid transparent;
  background-clip: content-box;
}
</style>
