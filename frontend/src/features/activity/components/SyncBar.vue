<script setup lang="ts">
/** 同步区：新鲜度 + 立即同步 + 账号管理弹层（解绑）+ 右侧账号入口。
 * 汇总视图为用户组下拉菜单；平台视图为该平台绑定账号的 ID（未绑定则
 * 显示「未绑定账号」），点击进入绑定 / 换绑。 */

import { computed, ref } from 'vue'
import { Link2, Plus, RefreshCw, Unlink, Users } from 'lucide-vue-next'
import { NButton, NPopover, NTooltip } from 'naive-ui'
import DeleteConfirmModal from '@/shared/components/DeleteConfirmModal.vue'
import UserGroupMenu from '@/features/activity/components/UserGroupMenu.vue'
import { useActivity } from '@/features/activity/store'
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
  unbind: [platform: PlatformId, handle: string]
}>()

const { platformName } = useActivity()

const removing = ref<BoundAccount | null>(null)

/** 平台视图下当前平台绑定的账号（每平台至多一个） */
const platformAccount = computed<BoundAccount | null>(() => {
  if (props.activePlatform === 'all') return null
  return props.accounts.find((a) => a.platform === props.activePlatform) ?? null
})

function stateLabel(acc: BoundAccount): string {
  if (acc.syncState === 'running') return '同步中'
  if (acc.syncState === 'error') return acc.syncError ?? '同步失败'
  return ''
}

function confirmUnbind(): void {
  if (!removing.value) return
  emit('unbind', removing.value.platform, removing.value.handle)
  removing.value = null
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
          @click="emit('sync')"
        >
          <RefreshCw :size="15" />
        </button>
      </template>
      立即同步
    </NTooltip>
    <NPopover trigger="click" placement="bottom-end">
      <template #trigger>
        <button type="button" class="tool-icon-btn" aria-label="账号管理">
          <Users :size="15" />
        </button>
      </template>
      <div class="account-panel">
        <div class="account-panel-title">已绑定账号</div>
        <div v-if="accounts.length === 0" class="account-empty">还没有绑定任何账号</div>
        <div v-for="acc in accounts" :key="`${acc.platform}/${acc.handle}`" class="account-row">
          <span class="account-platform">{{ platformName(acc.platform) }}</span>
          <span class="account-handle mono">{{ acc.handle }}</span>
          <span class="account-state" :class="acc.syncState">{{ stateLabel(acc) }}</span>
          <NTooltip :show-arrow="false">
            <template #trigger>
              <button
                type="button"
                class="account-unbind"
                aria-label="解绑"
                @click="removing = acc"
              >
                <Unlink :size="13" />
              </button>
            </template>
            解绑并删除本地数据
          </NTooltip>
        </div>
      </div>
    </NPopover>
    <UserGroupMenu v-if="activePlatform === 'all'" />
    <NTooltip v-else :show-arrow="false">
      <template #trigger>
        <NButton
          v-if="platformAccount"
          size="small"
          type="primary"
          secondary
          @click="emit('bind', platformAccount.platform)"
        >
          <template #icon><Link2 :size="14" /></template>
          <span class="bound-handle mono">{{ platformAccount.handle }}</span>
        </NButton>
        <NButton v-else size="small" dashed @click="emit('bind', activePlatform as PlatformId)">
          <template #icon><Plus :size="14" /></template>
          未绑定账号
        </NButton>
      </template>
      {{ platformAccount ? '点击换绑账号' : '点击绑定账号' }}
    </NTooltip>
    <DeleteConfirmModal
      :show="removing !== null"
      title="解绑账号"
      :target="removing ? `${platformName(removing.platform)}/${removing.handle}` : ''"
      @update:show="removing = null"
      @confirm="confirmUnbind"
    />
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

.account-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 240px;
}

.account-panel-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
}

.account-empty {
  font-size: 12px;
  color: var(--faint);
  padding: 6px 0;
}

.account-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
}

.account-platform {
  color: var(--muted);
  flex: none;
}

.account-handle {
  color: var(--text);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-state {
  font-size: 11px;
  color: var(--faint);
}

.account-state.error {
  color: #c63b57;
}

.account-unbind {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  margin-left: auto;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--faint);
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease;
}

.account-unbind:hover {
  color: #c63b57;
  background: hsl(350 60% 50% / 0.1);
}
</style>
