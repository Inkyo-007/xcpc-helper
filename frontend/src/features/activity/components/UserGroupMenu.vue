<script setup lang="ts">
/** 用户组菜单（汇总视图）：按钮显示当前用户 ID（与左侧用户信息卡一致），
 * 下拉菜单顶部为「新建用户组」，下方为用户组列表，点击切换；
 * 每个菜单项左侧有删除按钮（确认后删除该组档案，至少保留一个组）。 */

import { computed, h, nextTick, ref, watch, type VNodeChild } from 'vue'
import { Check, ChevronDown, Plus, Trash2, UserRound } from 'lucide-vue-next'
import { NButton, NDropdown, NInput, NModal, useMessage, type DropdownOption } from 'naive-ui'
import DeleteConfirmModal from '@/shared/components/DeleteConfirmModal.vue'
import { useProfile, useUserGroups } from '@/features/activity/profile'

const { profile } = useProfile()
const { groups, currentKey, createGroup, switchGroup, deleteGroup } = useUserGroups()
const message = useMessage()

const CREATE_KEY = '__create__'

const options = computed<DropdownOption[]>(() => [
  { label: '新建用户组', key: CREATE_KEY, icon: () => h(Plus, { size: 14 }) },
  { type: 'divider', key: 'divider' },
  ...groups.value.map((g) => ({
    label: g.name,
    key: g.key,
  })),
])

/** 用户组菜单项：左侧删除按钮 + 组名 + 右侧当前组勾选；
 * 删除按钮 stopPropagation，点击不触发切换 */
function renderLabel(option: DropdownOption): VNodeChild {
  const key = String(option.key)
  if (key === CREATE_KEY) return String(option.label)
  return h('span', { class: 'group-option' }, [
    h(
      'button',
      {
        type: 'button',
        class: 'group-delete',
        'aria-label': '删除用户组',
        onClick: (event: MouseEvent) => {
          event.stopPropagation()
          removingKey.value = key
        },
      },
      () => h(Trash2, { size: 13 }),
    ),
    h('span', { class: 'group-option-name' }, String(option.label)),
    key === currentKey.value ? h(Check, { size: 13, class: 'group-option-check' }) : null,
  ])
}

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

/* ---------- 删除用户组 ---------- */

const removingKey = ref<string | null>(null)
const removingGroup = computed(
  () => groups.value.find((g) => g.key === removingKey.value) ?? null,
)

function confirmRemove(): void {
  if (!removingGroup.value) return
  const name = removingGroup.value.name
  const error = deleteGroup(removingGroup.value.key)
  if (error) {
    message.error(error)
    return
  }
  removingKey.value = null
  message.success(`已删除用户组 ${name}`)
}
</script>

<template>
  <NDropdown
    trigger="click"
    placement="bottom-end"
    :options="options"
    :render-label="renderLabel"
    @select="onSelect"
  >
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

  <DeleteConfirmModal
    :show="removingGroup !== null"
    title="删除用户组"
    :target="removingGroup?.name ?? ''"
    @update:show="removingKey = null"
    @confirm="confirmRemove"
  />
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

<!-- 下拉菜单 teleport 到 body，scoped 样式够不到，菜单项内容用全局样式 -->
<style>
.group-option {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}

.group-delete {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex: none;
  margin-left: -4px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: var(--faint);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s ease, color 0.15s ease, background 0.15s ease;
}

.n-dropdown-option:hover .group-delete {
  opacity: 1;
}

.group-delete:hover {
  color: #c63b57;
  background: hsl(350 60% 50% / 0.1);
}

.group-option-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-option-check {
  margin-left: auto;
  flex: none;
  color: var(--accent-strong);
}
</style>
