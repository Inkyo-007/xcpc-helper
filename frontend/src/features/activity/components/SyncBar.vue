<script setup lang="ts">
/** 同步区：新鲜度 + 立即同步 + 编辑用户组入口（仅汇总视图）+ 右侧账号入口。
 * 汇总视图为用户组下拉菜单；平台视图为该平台绑定账号的 ID（未绑定则
 * 显示「未绑定账号」），点击进入绑定 / 换绑。
 * 立即同步的范围随视图：汇总视图同步全部平台（点击先弹确认，说明
 * 可能较慢），平台视图只同步该平台（直接触发）。 */

import { computed, ref } from 'vue'
import { Link2, Plus, RefreshCw, TriangleAlert, UserRoundPen } from 'lucide-vue-next'
import { NButton, NModal, NTooltip } from 'naive-ui'
import UserGroupMenu from '@/features/activity/components/UserGroupMenu.vue'
import { accountLabel } from '@/features/activity/store'
import type { PlatformScope } from '@/features/activity/store'
import type { BoundAccount, PlatformId } from '@/features/activity/types'

const props = defineProps<{
  lastSyncLabel: string
  syncing: boolean
  accounts: BoundAccount[]
  activePlatform: PlatformScope
}>()

const emit = defineEmits<{
  sync: []
  bind: [platform: PlatformId]
  'edit-group': []
}>()

/** 平台视图下当前平台绑定的账号（每平台至多一个） */
const platformAccount = computed<BoundAccount | null>(() => {
  if (props.activePlatform === 'all') return null
  return props.accounts.find((a) => a.platform === props.activePlatform) ?? null
})

/** 凭据过期（auth_expired）：账号按钮警示态，点击重新授权（走换绑路径） */
const authExpired = computed(
  () => platformAccount.value?.syncErrorCode === 'auth_expired',
)
/** 该平台账号同步中（首次全量可能数分钟）：按钮显示进行态 */
const accountSyncing = computed(() => platformAccount.value?.syncState === 'running')

/* ---------- 同步全部平台确认 ---------- */

const showSyncAllConfirm = ref(false)

function onSyncClick(): void {
  // 平台视图只同步当前平台，直接触发；汇总视图先确认
  if (props.activePlatform === 'all') showSyncAllConfirm.value = true
  else emit('sync')
}

function confirmSyncAll(): void {
  showSyncAllConfirm.value = false
  emit('sync')
}
</script>

<template>
  <div class="sync-bar">
    <span class="sync-label mono">{{ lastSyncLabel }}</span>
    <NTooltip :show-arrow="false">
      <template #trigger>
        <button
          type="button"
          class="tool-icon-btn"
          :class="{ spinning: syncing }"
          :disabled="syncing || accounts.length === 0"
          aria-label="立即同步"
          @click="onSyncClick"
        >
          <RefreshCw :size="15" />
        </button>
      </template>
      立即同步
    </NTooltip>
    <NTooltip v-if="activePlatform === 'all'" :show-arrow="false">
      <template #trigger>
        <button
          type="button"
          class="tool-icon-btn"
          aria-label="编辑用户组"
          @click="emit('edit-group')"
        >
          <UserRoundPen :size="15" />
        </button>
      </template>
      编辑用户组
    </NTooltip>
    <UserGroupMenu v-if="activePlatform === 'all'" />
    <NTooltip v-else :show-arrow="false">
      <template #trigger>
        <NButton
          v-if="platformAccount"
          size="small"
          :type="authExpired ? 'warning' : 'primary'"
          secondary
          :loading="accountSyncing"
          @click="emit('bind', platformAccount.platform)"
        >
          <template v-if="!accountSyncing" #icon>
            <TriangleAlert v-if="authExpired" :size="14" />
            <Link2 v-else :size="14" />
          </template>
          <span class="bound-handle mono">
            {{ accountSyncing ? '同步中' : authExpired ? '凭据过期' : accountLabel(platformAccount) }}
          </span>
        </NButton>
        <NButton v-else size="small" dashed @click="emit('bind', activePlatform as PlatformId)">
          <template #icon><Plus :size="14" /></template>
          未绑定账号
        </NButton>
      </template>
      {{
        accountSyncing
          ? `正在同步 ${accountLabel(platformAccount!)} 的数据，可能需要几分钟`
          : authExpired
            ? `登录凭据已过期（${accountLabel(platformAccount!)}），点击重新授权`
            : platformAccount
              ? '点击换绑账号'
              : '点击绑定账号'
      }}
    </NTooltip>
    <NModal
      :show="showSyncAllConfirm"
      preset="card"
      title="同步全部平台"
      class="create-modal"
      :style="{ width: 'min(420px, calc(100vw - 40px))' }"
      @update:show="showSyncAllConfirm = $event"
    >
      <div class="sync-all-body">
        <p class="sync-all-text">
          将依次同步全部 {{ accounts.length }} 个已绑定平台的训练数据，
          平台与数据量较多时可能需要等待一段时间，期间页面会显示加载遮罩。
        </p>
        <p class="sync-all-hint">只想同步单个平台时，可先切换到对应平台视图再点「立即同步」。</p>
      </div>
      <div class="modal-actions">
        <NButton size="small" quaternary @click="showSyncAllConfirm = false">取消</NButton>
        <NButton size="small" type="primary" @click="confirmSyncAll">
          <template #icon><RefreshCw :size="14" /></template>
          开始同步
        </NButton>
      </div>
    </NModal>
  </div>
</template>

<style scoped>
.sync-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.sync-label {
  font-size: 11.5px;
  color: var(--faint);
  margin-right: 2px;
  white-space: nowrap;
}

.bound-handle {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
  transition: color 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
}

.tool-icon-btn:hover:not(:disabled) {
  color: var(--accent-strong);
  border-color: var(--accent);
  transform: translateY(-1px);
}

.tool-icon-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.tool-icon-btn.spinning svg {
  animation: sync-spin 0.9s linear infinite;
}

@keyframes sync-spin {
  to {
    transform: rotate(360deg);
  }
}

.sync-all-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sync-all-text {
  margin: 0;
  font-size: 13px;
  color: var(--text);
}

.sync-all-hint {
  margin: 0;
  font-size: 12px;
  color: var(--faint);
}
</style>
