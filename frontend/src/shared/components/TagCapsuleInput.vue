<script setup lang="ts">
import { ref } from 'vue'
import { Plus } from 'lucide-vue-next'
import { NButton, NInput } from 'naive-ui'

const props = defineProps<{
  modelValue: string[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const draft = ref('')

function add(): void {
  const tag = draft.value.trim()
  if (!tag || props.modelValue.includes(tag)) {
    draft.value = ''
    return
  }
  emit('update:modelValue', [...props.modelValue, tag])
  draft.value = ''
}

function remove(index: number): void {
  emit(
    'update:modelValue',
    props.modelValue.filter((_, i) => i !== index),
  )
}
</script>

<template>
  <div class="tag-editor">
    <n-input
      v-model:value="draft"
      size="small"
      placeholder="输入标签，点右侧 + 添加"
      @keydown.enter.prevent="add"
    >
      <template #suffix>
        <n-button text size="tiny" aria-label="添加标签" @click="add">
          <template #icon><Plus :size="15" /></template>
        </n-button>
      </template>
    </n-input>
    <div v-if="modelValue.length" class="tag-capsules">
      <button
        v-for="(tag, index) in modelValue"
        :key="tag"
        type="button"
        class="tag-capsule"
        @click="remove(index)"
      >
        <span class="tag-text">{{ tag }}</span>
        <span class="tag-remove" aria-hidden="true">删除</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.tag-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tag-capsules {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-capsule {
  position: relative;
  padding: 2px 12px;
  border: 1px solid var(--border);
  border-radius: 99px;
  background: var(--surface);
  color: var(--muted);
  font-size: 12px;
  line-height: 1.7;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease;
}

.tag-capsule .tag-remove {
  position: absolute;
  inset: 0;
  display: none;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #d03050;
}

.tag-capsule:hover {
  border-color: #d03050;
}

.tag-capsule:hover .tag-text {
  visibility: hidden;
}

.tag-capsule:hover .tag-remove {
  display: inline-flex;
}
</style>
