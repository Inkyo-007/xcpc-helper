<script setup lang="ts">
import { Trash2 } from 'lucide-vue-next'
import { NButton, NModal } from 'naive-ui'

defineProps<{
  show: boolean
  /** 弹窗标题，如 "删除模板" / "删除版本" */
  title: string
  /** 将被删除的对象描述，如 "数据结构/并查集" */
  target: string
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  confirm: []
}>()
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="title"
    class="create-modal"
    :style="{ width: 'min(440px, calc(100vw - 40px))' }"
    @update:show="emit('update:show', $event)"
  >
    <div class="delete-confirm">
      <p class="delete-target">
        即将删除：<code>{{ target }}</code>
      </p>
      <p class="delete-warning">删除后无法找回，请确认不再需要该内容。</p>
    </div>
    <div class="modal-actions">
      <n-button @click="emit('update:show', false)">取消</n-button>
      <n-button type="error" :loading="loading" @click="emit('confirm')">
        <template #icon><Trash2 :size="15" /></template>
        确认删除
      </n-button>
    </div>
  </n-modal>
</template>

<style scoped>
.delete-confirm {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.delete-target {
  margin: 0;
  font-size: 13.5px;
  color: var(--text);
}

.delete-target code {
  font-family: var(--font-mono);
  font-size: 12.5px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 1px 6px;
}

.delete-warning {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--danger, #d03050);
}
</style>
