<script setup lang="ts">
/** 用户组菜单（汇总视图）：按钮显示当前用户 ID（与左侧用户信息卡一致），
 * 下拉菜单顶部为「新建用户组」，下方为用户组列表，点击切换。
 * 重命名与删除在「编辑用户组」弹窗中操作（见 UserGroupEditModal）。 */

import { computed, h, nextTick, ref, watch } from 'vue'
import { Check, ChevronDown, Plus, UserRound } from 'lucide-vue-next'
import { NButton, NDropdown, NInput, NModal, useMessage, type DropdownOption } from 'naive-ui'
import { useProfile, useUserGroups } from '@/features/activity/profile'

const { profile } = useProfile()
const { groups, currentKey, createGroup, switchGroup } = useUserGroups()
const message = useMessage()

const CREATE_KEY = '__create__'

const options = computed<DropdownOption[]>(() => [
  { label: '新建用户组', key: CREATE_KEY, icon: () => h(Plus, { size: 14 }) },
  { type: 'divider', key: 'divider' },
  ...groups.value.map((g) => ({
    label: g.name,
    key: g.key,
    icon: g.key === currentKey.value ? () => h(Check, { size: 14 }) : undefined,
  })),
])

function onSelect(key: string | number): void {
  if (key === CREATE_KEY) {
    void openCreate()
    return
  }
  switchGroup(String(key))
}

/* ---------- 新建用户组弹窗 ---------- */

const showCreate = ref(false)
const createName = ref('')
const createError = ref('')
const createInput = ref<InstanceType<typeof NInput> | null>(null)

watch(createName, () => {
  createError.value = ''
})

async function openCreate(): Promise<void> {
  createName.value = ''
  createError.value = ''
  showCreate.value = true
  await nextTick()
  createInput.value?.focus()
}

function confirmCreate(): void {
  const id = createName.value.trim()
  const error = createGroup(id)
  if (error) {
    createError.value = error
    return
  }
  showCreate.value = false
  message.success(`已创建并切换到用户组 ${id}`)
}
</script>

<template>
  <NDropdown trigger="click" placement="bottom-end" :options="options" @select="onSelect">
    <NButton size="small" type="primary" secondary>
      <template #icon><UserRound :size="14" /></template>
      <span class="group-name mono">{{ profile.name || '未设置 ID' }}</span>
      <ChevronDown :size="13" class="group-caret" />
    </NButton>
  </NDropdown>

  <NModal
    :show="showCreate"
    preset="card"
    title="新建用户组"
    class="create-modal"
    :style="{ width: 'min(400px, calc(100vw - 40px))' }"
    @update:show="showCreate = $event"
  >
    <div class="create-form">
      <NInput
        ref="createInput"
        v-model:value="createName"
        size="small"
        placeholder="输入用户组 ID"
        @keyup.enter="confirmCreate"
      />
      <p v-if="createError" class="create-error">{{ createError }}</p>
    </div>
    <div class="modal-actions">
      <NButton size="small" quaternary @click="showCreate = false">取消</NButton>
      <NButton size="small" type="primary" :disabled="!createName.trim()" @click="confirmCreate">
        <template #icon><Plus :size="14" /></template>
        创建
      </NButton>
    </div>
  </NModal>
</template>

<style scoped>
.group-name {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-caret {
  margin-left: 2px;
  flex: none;
}

.create-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.create-error {
  margin: 0;
  font-size: 12.5px;
  font-weight: 600;
  color: #c63b57;
}
</style>
