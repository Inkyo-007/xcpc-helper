<script setup lang="ts">
/** 编辑用户组弹窗（汇总视图工具条「编辑用户组」打开）：
 * 列表式交互——每项一行，左描述右操作。
 * · 重命名用户组：右侧输入框 + 保存（等价于用户信息卡编辑 ID）；
 * · 删除用户组：右侧删除按钮（DeleteConfirmModal 确认，删当前组后关闭弹窗）；
 * · 已绑定账号：每账号一行，右侧「换绑」按钮打开绑定弹窗（锁定该平台）。 */

import { computed, ref, watch } from 'vue'
import { Link2, PencilLine, Trash2 } from 'lucide-vue-next'
import { NButton, NInput, NModal, useMessage } from 'naive-ui'
import DeleteConfirmModal from '@/shared/components/DeleteConfirmModal.vue'
import { useActivity } from '@/features/activity/store'
import { useProfile, useUserGroups } from '@/features/activity/profile'
import type { BoundAccount, PlatformId } from '@/features/activity/types'

const props = defineProps<{
  show: boolean
  accounts: BoundAccount[]
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  bind: [platform: PlatformId]
}>()

const { platformName } = useActivity()
const { profile } = useProfile()
const { groups, currentKey, deleteGroup } = useUserGroups()
const message = useMessage()

/* ---------- 重命名 ---------- */

const renameDraft = ref('')
const renameError = ref('')

watch(
  () => props.show,
  (show) => {
    if (show) {
      renameDraft.value = profile.name
      renameError.value = ''
    }
  },
)

watch(renameDraft, () => {
  renameError.value = ''
})

/** 与其他组重名（当前组除外） */
const duplicated = computed(() =>
  groups.value.some((g) => g.key !== currentKey.value && g.name === renameDraft.value.trim()),
)

function confirmRename(): void {
  const id = renameDraft.value.trim()
  if (!id) {
    renameError.value = '请输入用户组 ID'
    return
  }
  if (duplicated.value) {
    renameError.value = '该用户组已存在'
    return
  }
  if (id === profile.name) return
  profile.name = id
  message.success(`已重命名为 ${id}`)
}

/* ---------- 删除 ---------- */

const showDelete = ref(false)

/** 仅剩一个用户组时禁止删除 */
const deleteDisabled = computed(() => groups.value.length <= 1)

function confirmDelete(): void {
  const name = profile.name
  const error = deleteGroup(currentKey.value)
  showDelete.value = false
  if (error) {
    message.error(error)
    return
  }
  message.success(`已删除用户组 ${name}`)
  // 删除的是当前组，弹窗随之关闭
  emit('update:show', false)
}

/* ---------- 换绑 ---------- */

function stateLabel(acc: BoundAccount): string {
  if (acc.syncState === 'running') return '同步中'
  if (acc.syncState === 'error') return acc.syncError ?? '同步失败'
  return ''
}
</script>

<template>
  <NModal
    :show="show"
    preset="card"
    title="编辑用户组"
    class="create-modal"
    :style="{ width: 'min(480px, calc(100vw - 40px))' }"
    @update:show="emit('update:show', $event)"
  >
    <div class="edit-list">
      <div class="edit-row">
        <div class="edit-desc">
          <span class="edit-title">重命名用户组</span>
          <span class="edit-hint">修改当前用户组的 ID（数据归属不变）</span>
        </div>
        <div class="edit-action">
          <NInput
            v-model:value="renameDraft"
            size="small"
            class="rename-input"
            placeholder="输入用户组 ID"
            @keyup.enter="confirmRename"
          />
          <NButton
            size="small"
            type="primary"
            secondary
            :disabled="!renameDraft.trim() || renameDraft.trim() === profile.name"
            @click="confirmRename"
          >
            <template #icon><PencilLine :size="14" /></template>
            保存
          </NButton>
        </div>
      </div>
      <p v-if="renameError" class="edit-error">{{ renameError }}</p>

      <div class="edit-row">
        <div class="edit-desc">
          <span class="edit-title">删除用户组</span>
          <span class="edit-hint">删除当前用户组的档案（ID / 签名 / 头像），至少保留一个组</span>
        </div>
        <div class="edit-action">
          <NButton size="small" type="error" secondary :disabled="deleteDisabled" @click="showDelete = true">
            <template #icon><Trash2 :size="14" /></template>
            删除
          </NButton>
        </div>
      </div>

      <div class="edit-section-title">已绑定账号</div>
      <div v-if="accounts.length === 0" class="edit-empty">还没有绑定任何账号</div>
      <div v-for="acc in accounts" :key="`${acc.platform}/${acc.handle}`" class="edit-row">
        <div class="edit-desc">
          <span class="edit-title">
            {{ platformName(acc.platform) }}
            <span class="account-handle mono">{{ acc.handle }}</span>
          </span>
          <span v-if="stateLabel(acc)" class="edit-hint account-state" :class="acc.syncState">
            {{ stateLabel(acc) }}
          </span>
        </div>
        <div class="edit-action">
          <NButton size="small" secondary @click="emit('bind', acc.platform)">
            <template #icon><Link2 :size="14" /></template>
            换绑
          </NButton>
        </div>
      </div>
    </div>

    <DeleteConfirmModal
      :show="showDelete"
      title="删除用户组"
      :target="profile.name"
      @update:show="showDelete = $event"
      @confirm="confirmDelete"
    />
  </NModal>
</template>

<style scoped>
.edit-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.edit-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
}

.edit-desc {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.edit-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
}

.edit-hint {
  font-size: 11.5px;
  color: var(--faint);
}

.edit-action {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

.rename-input {
  width: 160px;
}

.edit-error {
  margin: -2px 0 0;
  font-size: 12.5px;
  font-weight: 600;
  color: #c63b57;
}

.edit-section-title {
  margin-top: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  letter-spacing: 0.02em;
}

.edit-empty {
  padding: 6px 0;
  font-size: 12px;
  color: var(--faint);
}

.account-handle {
  font-size: 12px;
  color: var(--muted);
}

.account-state.error {
  color: #c63b57;
}
</style>
