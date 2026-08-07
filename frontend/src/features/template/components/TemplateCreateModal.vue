<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Plus } from 'lucide-vue-next'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  useMessage,
  type FormInst,
  type SelectOption,
} from 'naive-ui'
import { ApiError } from '@/shared/api/client'
import { useTemplates } from '@/features/template/store'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  created: [id: string]
}>()

const message = useMessage()
const { categories, createTemplate } = useTemplates()

const formRef = ref<FormInst | null>(null)
const submitting = ref(false)
const form = reactive({
  category: null as string | null,
  name: '',
})

// 分类选项来自后端动态数据（排除内置的"全部"），允许输入新分类名
const catOptions = computed<SelectOption[]>(() =>
  categories.value
    .filter((c) => c.id !== 'all')
    .map((c) => ({ label: c.name, value: c.id })),
)

const rules = {
  category: { required: true, message: '请选择或输入分类', trigger: ['blur', 'change'] },
  name: { required: true, message: '请输入模板名（主标签）', trigger: ['input', 'blur'] },
}

// 每次打开时重置表单
watch(
  () => props.show,
  (show) => {
    if (show) {
      form.category = null
      form.name = ''
    }
  },
)

async function submit(): Promise<void> {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  if (!form.category) return
  submitting.value = true
  try {
    const id = await createTemplate({ category: form.category, name: form.name.trim() })
    message.success(`已创建空模板「${form.name.trim()}」，展开后点 + 添加版本`)
    emit('update:show', false)
    emit('created', id)
  } catch (err) {
    // 失败时弹窗不关闭、表单保留，便于修正后重试
    if (err instanceof ApiError && err.code === 'conflict') {
      message.error(err.message)
    } else {
      message.error(err instanceof Error ? err.message : '创建失败，请重试')
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="新增模板"
    class="create-modal"
    :style="{ width: 'min(480px, calc(100vw - 40px))' }"
    @update:show="emit('update:show', $event)"
  >
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" size="small">
      <n-form-item label="分类" path="category">
        <n-select
          v-model:value="form.category"
          :options="catOptions"
          filterable
          tag
          placeholder="选择已有分类，或输入新分类名"
        />
      </n-form-item>
      <n-form-item label="模板名（主标签）" path="name">
        <n-input v-model:value="form.name" placeholder="例如：线段树" />
      </n-form-item>
      <div class="modal-actions">
        <n-button @click="emit('update:show', false)">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="submit">
          <template #icon><Plus :size="15" /></template>
          创建
        </n-button>
      </div>
    </n-form>
  </n-modal>
</template>
