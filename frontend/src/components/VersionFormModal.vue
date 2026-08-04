<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { FileUp, Save } from 'lucide-vue-next'
import {
  NButton,
  NDatePicker,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NRadioButton,
  NRadioGroup,
  NSelect,
  useMessage,
  type FormInst,
  type SelectOption,
} from 'naive-ui'
import { ApiError } from '@/api/client'
import CodeEditor from '@/components/CodeEditor.vue'
import TagCapsuleInput from '@/components/TagCapsuleInput.vue'
import { useTemplates } from '@/composables/useTemplates'
import {
  ROOT_VERSION_TOKEN,
  type TemplateVariant,
  type VersionUpsertPayload,
} from '@/types'

const props = defineProps<{
  show: boolean
  /** create：新建版本；edit：编辑现有版本 */
  mode: 'create' | 'edit'
  /** 所属模板 id（"分类/模板名"） */
  templateId: string
  /** 编辑模式下的当前版本；新建时为 null */
  variant?: TemplateVariant | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  /** 保存成功：返回最新详情与提交时使用的版本名（用于选中） */
  saved: [detailId: string, versionName: string]
}>()

const message = useMessage()
const { saveVersion } = useTemplates()

/** 后端支持的代码扩展名（与 scanner.CODE_EXTENSIONS 一致） */
const EXT_OPTIONS: SelectOption[] = [
  { label: 'C++ (.cpp)', value: 'cpp' },
  { label: 'C (.c)', value: 'c' },
  { label: 'Python (.py)', value: 'py' },
  { label: 'Java (.java)', value: 'java' },
  { label: 'C++ (.cc)', value: 'cc' },
  { label: 'C++ (.cxx)', value: 'cxx' },
  { label: '头文件 (.h)', value: 'h' },
  { label: '头文件 (.hpp)', value: 'hpp' },
]
const SUPPORTED_EXTS = EXT_OPTIONS.map((o) => o.value as string)

/** 顶层单版本：代码直接在模板目录下（variant.id === templateId），不支持改名 */
const isTopLevel = computed(
  () => props.mode === 'edit' && props.variant?.id === props.templateId,
)

const formRef = ref<FormInst | null>(null)
const submitting = ref(false)
const codeInputMode = ref<'manual' | 'upload'>('manual')
const readmeInputMode = ref<'manual' | 'upload'>('manual')
const codeFileInput = ref<HTMLInputElement | null>(null)
const readmeFileInput = ref<HTMLInputElement | null>(null)

const form = reactive({
  name: '',
  updated: null as number | null,
  tags: [] as string[],
  source: '',
  page: '',
  priority: 2,
  ext: 'cpp',
  fileName: '',
  code: '',
  readme: '',
})

const rules = {
  name: { required: true, message: '请输入版本名（副标签）', trigger: ['input', 'blur'] },
  code: { required: true, message: '代码不能为空', trigger: ['blur'] },
}

function toTimestamp(iso: string | null): number | null {
  if (!iso) return null
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).getTime()
}

function toIsoDate(ts: number): string {
  const date = new Date(ts)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** 打开弹窗时按模式初始化表单 */
watch(
  () => props.show,
  (show) => {
    if (!show) return
    codeInputMode.value = 'manual'
    readmeInputMode.value = 'manual'
    if (props.mode === 'edit' && props.variant) {
      const v = props.variant
      form.name = v.id === props.templateId ? '' : v.name
      form.updated = toTimestamp(v.updated)
      form.tags = [...v.tags]
      form.source = v.src ?? ''
      form.page = v.page ?? ''
      form.priority = v.priority
      // 扩展名以文件名后缀为准（.h/.hpp 的 lang 也是 cpp，直接取 lang 会错位）
      const suffix = v.file.includes('.')
        ? (v.file.split('.').pop()?.toLowerCase() ?? '')
        : ''
      form.ext = SUPPORTED_EXTS.includes(suffix) ? suffix : v.lang
      form.fileName = v.file
      form.code = v.code
      form.readme = v.body
    } else {
      form.name = ''
      form.updated = Date.now() // 更新日期默认当天，可手动修改
      form.tags = []
      form.source = ''
      form.page = ''
      form.priority = 2
      form.ext = 'cpp'
      form.fileName = ''
      form.code = ''
      form.readme = ''
    }
  },
)

// 切换扩展名时，若文件名未自定义则跟随默认值
watch(
  () => form.ext,
  (ext, prev) => {
    if (!form.fileName || form.fileName === `code.${prev}`) {
      form.fileName = `code.${ext}`
    }
  },
)

/** 上传代码文件：读取文本并按扩展名推断语言 */
async function onCodeFilePicked(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
  if (!SUPPORTED_EXTS.includes(ext)) {
    message.error(`不支持的文件类型 .${ext}（支持：${SUPPORTED_EXTS.join(' / ')}）`)
    return
  }
  form.code = await file.text()
  form.ext = ext
  form.fileName = file.name
  message.success(`已载入 ${file.name}`)
}

/** 上传 README 文件：文件内容仅作为说明正文，元数据仍以表单为准 */
async function onReadmeFilePicked(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  form.readme = await file.text()
  message.success(`已载入 ${file.name}（仅作为说明正文）`)
}

async function submit(): Promise<void> {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  const versionName = isTopLevel.value ? '' : form.name.trim()
  const payload: VersionUpsertPayload = {
    name: props.mode === 'create' ? versionName : isTopLevel.value ? null : versionName,
    file: form.fileName.trim() || null,
    ext: form.ext,
    code: form.code,
    meta: {
      updated: form.updated ? toIsoDate(form.updated) : null,
      tags: form.tags,
      source: form.source.trim() || null,
      page: form.page.trim() || null,
      priority: form.priority,
    },
    body: form.readme,
  }
  const token =
    props.mode === 'create'
      ? ''
      : isTopLevel.value
        ? ROOT_VERSION_TOKEN
        : (props.variant?.name ?? '')
  submitting.value = true
  try {
    const detail = await saveVersion(
      props.templateId,
      token,
      payload,
      props.mode === 'create',
    )
    message.success(props.mode === 'create' ? '版本已创建' : '版本已保存')
    emit('update:show', false)
    // 顶层单版本没有副标签名，选中时回退到模板名（与其显示名一致）
    emit('saved', detail.id, versionName || detail.name)
  } catch (err) {
    // 失败时弹窗不关闭、表单保留
    if (err instanceof ApiError) {
      message.error(err.message)
    } else {
      message.error(err instanceof Error ? err.message : '保存失败，请重试')
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
    :title="mode === 'create' ? '新增版本' : '编辑版本'"
    class="create-modal"
    :style="{ width: 'min(760px, calc(100vw - 40px))' }"
    @update:show="emit('update:show', $event)"
  >
    <n-form ref="formRef" :model="form" :rules="rules" label-placement="top" size="small">
      <div class="form-grid">
        <n-form-item v-if="!isTopLevel" label="版本名（副标签）" path="name">
          <n-input v-model:value="form.name" placeholder="例如：懒标记 / 路径压缩" />
        </n-form-item>
        <n-form-item label="更新日期">
          <n-date-picker
            v-model:value="form.updated"
            type="date"
            clearable
            style="width: 100%"
          />
        </n-form-item>
        <n-form-item label="优先级（1-9）">
          <n-input-number
            v-model:value="form.priority"
            :min="1"
            :max="9"
            style="width: 100%"
          />
        </n-form-item>
        <n-form-item label="来源">
          <n-input v-model:value="form.source" placeholder="例如：洛谷 P3383" />
        </n-form-item>
        <n-form-item label="来源链接（填写来源后可用）">
          <n-input
            v-model:value="form.page"
            :disabled="!form.source.trim()"
            placeholder="https://…"
          />
        </n-form-item>
      </div>

      <n-form-item label="标签">
        <TagCapsuleInput v-model="form.tags" />
      </n-form-item>

      <n-form-item label="代码" path="code">
        <div class="field-block">
          <div class="field-toolbar">
            <n-radio-group v-model:value="codeInputMode" size="small">
              <n-radio-button value="manual">手动输入</n-radio-button>
              <n-radio-button value="upload">上传文件</n-radio-button>
            </n-radio-group>
            <template v-if="codeInputMode === 'manual'">
              <n-select
                v-model:value="form.ext"
                :options="EXT_OPTIONS"
                size="small"
                style="width: 150px"
              />
              <n-input
                v-model:value="form.fileName"
                size="small"
                placeholder="代码文件名"
                style="width: 180px"
              />
            </template>
            <n-button v-else size="small" @click="codeFileInput?.click()">
              <template #icon><FileUp :size="14" /></template>
              选择代码文件
            </n-button>
            <input
              ref="codeFileInput"
              type="file"
              hidden
              accept=".cpp,.cc,.cxx,.c,.h,.hpp,.py,.java"
              @change="onCodeFilePicked"
            />
          </div>
          <CodeEditor v-model="form.code" />
        </div>
      </n-form-item>

      <n-form-item label="说明（Markdown）">
        <div class="field-block">
          <div class="field-toolbar">
            <n-radio-group v-model:value="readmeInputMode" size="small">
              <n-radio-button value="manual">手动输入</n-radio-button>
              <n-radio-button value="upload">上传文件</n-radio-button>
            </n-radio-group>
            <n-button
              v-if="readmeInputMode === 'upload'"
              size="small"
              @click="readmeFileInput?.click()"
            >
              <template #icon><FileUp :size="14" /></template>
              选择 Markdown 文件
            </n-button>
            <input
              ref="readmeFileInput"
              type="file"
              hidden
              accept=".md,.markdown,.txt"
              @change="onReadmeFilePicked"
            />
          </div>
          <n-input
            v-model:value="form.readme"
            type="textarea"
            :rows="4"
            class="modal-code-field"
            placeholder="模板说明、复杂度、注意事项……"
          />
        </div>
      </n-form-item>

      <div class="modal-actions">
        <n-button @click="emit('update:show', false)">取消</n-button>
        <n-button type="primary" :loading="submitting" @click="submit">
          <template #icon><Save :size="15" /></template>
          {{ mode === 'create' ? '创建版本' : '保存修改' }}
        </n-button>
      </div>
    </n-form>
  </n-modal>
</template>

<style scoped>
.field-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.field-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
