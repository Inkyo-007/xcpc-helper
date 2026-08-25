<script setup lang="ts">
/** 平台账号管理弹窗（平台视图右上角账号按钮打开）：
 * 列表式交互——每项一行，左描述右操作（与编辑用户组弹窗同构）：
 * · 当前账号：展示名 + 同步状态（纯信息行）；
 * · 换绑账号：打开绑定弹窗（新账号替换旧账号及其本地数据）；
 * · 解绑账号：确认后删除该账号全部本地数据（提交记录与凭据，不可找回）。 */

import { ref, watch } from 'vue'
import { KeyRound, Link2, Unlink } from 'lucide-vue-next'
import { NButton, NModal } from 'naive-ui'
import DeleteConfirmModal from '@/shared/components/DeleteConfirmModal.vue'
import { accountLabel, useActivity } from '@/features/activity/store'
import type { BoundAccount, PlatformId } from '@/features/activity/types'

const props = defineProps<{
  show: boolean
  /** 目标账号；null 时弹窗不渲染内容 */
  account: BoundAccount | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  bind: [platform: PlatformId]
  unbind: [platform: PlatformId, handle: string]
  'update-credentials': [account: BoundAccount]
}>()

const { platformName } = useActivity()

const confirmingUnbind = ref(false)

watch(
  () => props.show,
  (show) => {
    if (!show) confirmingUnbind.value = false
  },
)

function stateLabel(acc: BoundAccount): string {
  if (acc.syncState === 'running') return '同步中'
  if (acc.syncState === 'error') {
    if (acc.syncErrorCode === 'auth_expired') return '凭据过期'
    return acc.syncError ?? '同步失败'
  }
  return '同步正常'
}

function confirmUnbind(): void {
  if (!props.account) return
  confirmingUnbind.value = false
  emit('update:show', false)
  emit('unbind', props.account.platform, props.account.handle)
}
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    :title="`${platformName(account?.platform ?? 'codeforces')} 账号管理`"
    class="create-modal"
    :style="{ width: 'min(440px, calc(100vw - 40px))' }"
    @update:show="emit('update:show', $event)"
  >
    <div v-if="account" class="acct-list">
      <div class="acct-row">
        <div class="acct-desc">
          <span class="acct-title">
            当前账号
            <span class="acct-handle mono">{{ accountLabel(account) }}</span>
          </span>
          <span class="acct-hint" :class="account.syncState">{{ stateLabel(account) }}</span>
        </div>
      </div>

      <div class="acct-row">
        <div class="acct-desc">
          <span class="acct-title">更新凭据</span>
          <span class="acct-hint">重新录入 cookie 等登录凭据，保留已有数据</span>
        </div>
        <div class="acct-action">
          <NButton
            size="small"
            secondary
            type="warning"
            @click="emit('update:show', false); emit('update-credentials', account)"
          >
            <template #icon><KeyRound :size="14" /></template>
            更新凭据
          </NButton>
        </div>
      </div>

      <div class="acct-row">
        <div class="acct-desc">
          <span class="acct-title">换绑账号</span>
          <span class="acct-hint">绑定新账号替换当前账号，并删除其本地数据</span>
        </div>
        <div class="acct-action">
          <NButton
            size="small"
            secondary
            @click="emit('update:show', false); emit('bind', account.platform)"
          >
            <template #icon><Link2 :size="14" /></template>
            换绑
          </NButton>
        </div>
      </div>

      <div class="acct-row">
        <div class="acct-desc">
          <span class="acct-title">解绑账号</span>
          <span class="acct-hint">删除该账号的全部本地数据（提交记录与凭据），不可找回</span>
        </div>
        <div class="acct-action">
          <NButton size="small" type="error" secondary @click="confirmingUnbind = true">
            <template #icon><Unlink :size="14" /></template>
            解绑
          </NButton>
        </div>
      </div>
    </div>

    <DeleteConfirmModal
      :show="confirmingUnbind"
      title="解绑账号"
      :target="account ? `${platformName(account.platform)}/${accountLabel(account)}` : ''"
      @update:show="confirmingUnbind = $event"
      @confirm="confirmUnbind"
    />
  </NModal>
</template>

<style scoped>
.acct-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.acct-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.acct-desc {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.acct-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
}

.acct-hint {
  font-size: 11.5px;
  color: var(--faint);
}

.acct-hint.error {
  color: #c63b57;
}

.acct-action {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

.acct-handle {
  font-size: 12px;
  color: var(--muted);
}
</style>
