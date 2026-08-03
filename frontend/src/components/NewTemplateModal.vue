<script setup lang="ts">
import { reactive, ref } from 'vue'
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
import type { LangId, NewTemplateInput } from '@/types'

defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  create: [input: NewTemplateInput]
}>()

const message = useMessage()
const formRef = ref<FormInst | null>(null)
const form = reactive({
  name: '',
  cat: 'ds' as string,
  lang: 'cpp' as LangId,
  src: '',
  desc: '',
  code: '',
})

const rules = {
  name: { required: true, message: '请输入模板名称', trigger: ['input', 'blur'] },
  code: { required: true, message: '请输入模板代码', trigger: ['input', 'blur'] },
}

const catOptions: SelectOption[] = [
  { label: '数据结构', value: 'ds' },
  { label: '图论', value: 'graph' },
  { label: '字符串', value: 'string' },
  { label: '数学', value: 'math' },
  { label: '动态规划', value: 'dp' },
  { label: '其他', value: 'misc' },
]

const langOptions: SelectOption[] = [
  { label: 'C++', value: 'cpp' },
  { label: 'Python', value: 'py' },
  { label: 'Java', value: 'java' },
  { label: 'C', value: 'c' },
]

async function submit(): Promise<void> {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  emit('create', { ...form })
  emit('update:show', false)
  message.success('模板已加入本地模板库')
  form.name = ''
  form.src = ''
  form.desc = ''
  form.code = ''
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="新建模板"
    class="create-modal"
    :style="{ width: 'min(720px, calc(100vw - 40px))' }"
    @update:show="emit('update:show', $event)"
  >
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" size="small">
      <div class="form-grid">
        <n-form-item label="模板名称" path="name">
          <n-input v-model:value="form.name" placeholder="例如：线段树（懒标记）" />
        </n-form-item>
        <n-form-item label="分类" path="cat">
          <n-select v-model:value="form.cat" :options="catOptions" />
        </n-form-item>
        <n-form-item label="语言" path="lang">
          <n-select v-model:value="form.lang" :options="langOptions" />
        </n-form-item>
        <n-form-item label="来源" path="src">
          <n-input v-model:value="form.src" placeholder="题目或仓库来源" />
        </n-form-item>
        <n-form-item label="说明" path="desc">
          <n-input v-model:value="form.desc" placeholder="一句话说明注意事项" />
        </n-form-item>
      </div>
      <n-form-item label="代码" path="code">
        <n-input
          v-model:value="form.code"
          type="textarea"
          :rows="10"
          class="modal-code-field"
          placeholder="粘贴 C++ 模板代码"
        />
      </n-form-item>
      <div class="modal-actions">
        <n-button @click="emit('update:show', false)">取消</n-button>
        <n-button type="primary" @click="submit">
          <template #icon><Plus :size="15" /></template>
          保存模板
        </n-button>
      </div>
    </n-form>
  </n-modal>
</template>
