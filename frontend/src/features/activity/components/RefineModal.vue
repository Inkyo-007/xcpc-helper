<script setup lang="ts">
/** 精细化同步弹窗（REFINE_VERDICT 能力平台，当前为洛谷）：三态。
 *
 * - 未开始（idle/stopped）：功能说明 + 按存量 UNAC×5s 的耗时预估 +
 *   可随时中止提示 → 确认开始；
 * - 进行中（running）：进度百分比 + 中止按钮（普通同步进行时自动暂停）；
 * - 已完成（done）：「随同步自动精化」开关（普通同步完成后自动精化新增 UNAC）。
 *
 * 打开期间轮询状态（运行中 1s，其余仅打开时拉一次）。
 */

import { computed, ref, watch } from 'vue'
import { Sparkles, Square } from 'lucide-vue-next'
import { NButton, NModal, NSwitch } from 'naive-ui'
import {
  fetchRefineStatus,
  setRefineAuto,
  startRefine,
  stopRefine,
} from '@/features/activity/api'
import { estimateRefineDuration } from '@/features/activity/model/refine'
import type { BoundAccount, RefineStatus } from '@/features/activity/types'

const props = defineProps<{
  show: boolean
  account: BoundAccount | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  /** 精化从未完成态进入完成态（父级刷新数据使新结果可见） */
  done: []
}>()

const status = ref<RefineStatus | null>(null)
const operating = ref(false)
const errorText = ref('')

const state = computed(() => status.value?.state ?? 'idle')
const percent = computed(() => {
  const s = status.value
  if (!s || s.total <= 0) return 100
  return Math.min(100, Math.round((s.done / s.total) * 100))
})
const estimate = computed(() => estimateRefineDuration(status.value?.total ?? 0))

/* 精化从未完成态进入完成态时通知父级刷新数据（新 verdict 落盘可见） */
let wasRunning = false
watch(state, (now) => {
  if (now === 'running') wasRunning = true
  if (now === 'done' && wasRunning) emit('done')
  if (now !== 'running') wasRunning = false
})

let pollTimer: ReturnType<typeof setInterval> | null = null

async function refresh(): Promise<void> {
  if (!props.account) return
  try {
    status.value = await fetchRefineStatus(props.account.platform, props.account.handle)
  } catch {
    /* 状态拉取失败保持旧值 */
  }
}

watch(
  () => props.show,
  (show) => {
    if (show) {
      errorText.value = ''
      void refresh()
      // 仅运行中需要轮询；状态转移后由 refresh 内的调度重建
      pollTimer = setInterval(() => {
        if (state.value === 'running') void refresh()
      }, 1000)
    } else if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  },
)

async function start(): Promise<void> {
  if (!props.account) return
  operating.value = true
  errorText.value = ''
  try {
    await startRefine(props.account.platform, props.account.handle)
    await refresh()
  } catch (e) {
    errorText.value = e instanceof Error ? e.message : '启动失败，请稍后重试'
  } finally {
    operating.value = false
  }
}

async function stop(): Promise<void> {
  if (!props.account) return
  operating.value = true
  errorText.value = ''
  try {
    await stopRefine(props.account.platform, props.account.handle)
    await refresh()
  } catch (e) {
    errorText.value = e instanceof Error ? e.message : '中止失败，请稍后重试'
  } finally {
    operating.value = false
  }
}

async function toggleAuto(enabled: boolean): Promise<void> {
  if (!props.account) return
  try {
    status.value = await setRefineAuto(props.account.platform, props.account.handle, enabled)
  } catch (e) {
    errorText.value = e instanceof Error ? e.message : '设置失败，请稍后重试'
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="精细化同步"
    class="create-modal"
    :style="{ width: 'min(440px, calc(100vw - 40px))' }"
    @update:show="emit('update:show', $event)"
  >
    <div class="refine-body">
      <!-- 未开始 / 已中止 -->
      <template v-if="state === 'idle' || state === 'stopped'">
        <p class="refine-text">
          洛谷记录列表只区分 AC / CE / 未通过（UNAC）。精细化同步会逐条拉取
          UNAC 记录的详情，把「未通过」还原为具体结果（WA / TLE / RE 等）。
        </p>
        <p v-if="status && status.total > 0" class="refine-text">
          当前有 <b>{{ status.total }}</b> 条待精化记录，预计耗时
          <b>{{ estimate }}</b>（每条间隔 5 秒，期间可随时中止、自动续扫；
          普通同步优先——同步进行时精化会自动暂停）。
        </p>
        <p v-else class="refine-text">当前没有待精化的记录。</p>
        <p v-if="state === 'stopped'" class="refine-hint">
          上次已中止（已精化 {{ status!.done }} 条），进度保留，可继续。
        </p>
      </template>

      <!-- 进行中 -->
      <template v-else-if="state === 'running'">
        <p class="refine-text">
          正在精化：{{ status!.done }} / {{ status!.total }}（{{ percent }}%）
        </p>
        <div class="refine-progress">
          <div class="refine-progress-bar" :style="{ width: `${percent}%` }" />
        </div>
        <p class="refine-hint">
          可随时中止，进度保留；普通同步进行时会自动暂停，结束后继续。
        </p>
      </template>

      <!-- 已完成 -->
      <template v-else>
        <p class="refine-text">全部 UNAC 记录已精化完成。</p>
        <label class="refine-auto">
          <n-switch
            :value="status?.auto ?? false"
            size="small"
            @update:value="toggleAuto"
          />
          <span class="refine-auto-text">
            随同步自动精化
            <span class="refine-hint">普通同步完成后自动精化新增记录</span>
          </span>
        </label>
      </template>

      <p v-if="errorText" class="refine-error">{{ errorText }}</p>
    </div>
    <div class="modal-actions">
      <n-button size="small" quaternary @click="emit('update:show', false)">关闭</n-button>
      <n-button
        v-if="state === 'idle' || state === 'stopped'"
        size="small"
        type="primary"
        :loading="operating"
        :disabled="!status || status.total === 0"
        @click="start"
      >
        <template #icon><Sparkles :size="14" /></template>
        {{ state === 'stopped' ? '继续精化' : '开始精化' }}
      </n-button>
      <n-button
        v-else-if="state === 'running'"
        size="small"
        type="error"
        secondary
        :loading="operating"
        @click="stop"
      >
        <template #icon><Square :size="14" /></template>
        中止
      </n-button>
    </div>
  </n-modal>
</template>

<style scoped>
.refine-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.refine-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text);
}

.refine-hint {
  margin: 0;
  font-size: 11.5px;
  color: var(--faint);
}

.refine-progress {
  height: 6px;
  border-radius: 3px;
  background: var(--surface-2);
  overflow: hidden;
}

.refine-progress-bar {
  height: 100%;
  border-radius: 3px;
  background: var(--accent);
  transition: width 0.4s ease;
}

.refine-auto {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.refine-auto-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  font-size: 13px;
  color: var(--text);
}

.refine-error {
  margin: 0;
  font-size: 12.5px;
  font-weight: 600;
  color: #c63b57;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
</style>
