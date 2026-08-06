<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Upload } from 'lucide-vue-next'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  useMessage,
} from 'naive-ui'
import type { BookBlock, TemplateBlock } from '@/types'

const props = defineProps<{
  show: boolean
  block: BookBlock | null
}>()

const emit = defineEmits<{
  'update:show': [show: boolean]
  save: [block: BookBlock]
}>()

const message = useMessage()
const draft = ref<BookBlock | null>(null)
const imageInput = ref<HTMLInputElement | null>(null)

const headingDraft = computed(() => (draft.value?.type === 'heading' ? draft.value : null))
const templateDraft = computed(() => (draft.value?.type === 'template' ? draft.value : null))
const markdownDraft = computed(() => (draft.value?.type === 'markdown' ? draft.value : null))
const imageDraft = computed(() => (draft.value?.type === 'image' ? draft.value : null))

const LEVEL_OPTIONS = [1, 2, 3, 4, 5, 6].map((level) => ({
  label: `H${level}`,
  value: level,
}))

const BODY_OPTIONS = [
  { label: '跟随册级默认', value: 'default' },
  { label: '包含说明', value: 'include' },
  { label: '不包含说明', value: 'exclude' },
]

watch(
  () => props.show,
  (show) => {
    if (show && props.block) {
      // 块对象经 Vue 响应式代理包裹，structuredClone 无法克隆 Proxy
      draft.value = JSON.parse(JSON.stringify(props.block)) as BookBlock
    }
  },
)

const title = computed(() => {
  if (!props.block) return ''
  const map = {
    heading: '编辑章节',
    template: '编辑模板条目',
    markdown: '编辑文字块',
    image: '编辑图片块',
    page_break: '分页符',
  }
  return map[props.block.type]
})

function bodyMode(block: TemplateBlock): string {
  return block.include_body === null ? 'default' : block.include_body ? 'include' : 'exclude'
}

function onBodyModeChange(value: string, block: TemplateBlock | null): void {
  if (!block) return
  block.include_body = value === 'default' ? null : value === 'include'
}

function replaceImage(): void {
  imageInput.value?.click()
}

function onImagePicked(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  const block = draft.value
  if (file && block && block.type === 'image') {
    block.src = URL.createObjectURL(file)
    if (!block.caption) block.caption = file.name.replace(/\.[^.]+$/, '')
  }
  input.value = ''
}

function save(): void {
  const block = draft.value
  if (!block) return
  if (block.type === 'heading' && !block.title.trim()) {
    message.error('章节标题不能为空')
    return
  }
  emit('save', block)
  emit('update:show', false)
}

function setHeadingTitle(value: string): void {
  if (headingDraft.value) headingDraft.value.title = value
}

function setHeadingLevel(value: number): void {
  if (headingDraft.value) headingDraft.value.heading_level = value
}

function setTemplateTitle(value: string): void {
  if (templateDraft.value) templateDraft.value.title = value || null
}

function setTemplateLevel(value: number): void {
  if (templateDraft.value) templateDraft.value.heading_level = value
}

function setMarkdownTitle(value: string): void {
  if (markdownDraft.value) markdownDraft.value.title = value || null
}

function setMarkdownContent(value: string): void {
  if (markdownDraft.value) markdownDraft.value.content = value
}

function setImageCaption(value: string): void {
  if (imageDraft.value) imageDraft.value.caption = value || null
}

function setImageWidth(value: string): void {
  if (imageDraft.value) imageDraft.value.width = value
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    class="create-modal pb-editor-modal"
    :title="title"
    :style="{ width: '540px' }"
    @update:show="emit('update:show', $event)"
  >
    <template v-if="draft">
      <n-form label-placement="top" size="small">
        <template v-if="headingDraft">
          <n-form-item label="标题">
            <n-input :value="headingDraft.title" maxlength="40" @update:value="setHeadingTitle" />
          </n-form-item>
          <n-form-item label="标题级别">
            <n-select
              :value="headingDraft.heading_level"
              class="pb-editor-level"
              :options="LEVEL_OPTIONS"
              @update:value="setHeadingLevel"
            />
          </n-form-item>
        </template>

        <template v-else-if="templateDraft">
          <div class="pb-editor-template-info">
            <span class="pb-editor-template-name">{{ templateDraft.resolved?.name }}</span>
            <span class="pb-editor-template-version">{{ templateDraft.resolved?.version_name }}</span>
            <span class="pb-editor-template-lang">{{ templateDraft.resolved?.lang }}</span>
          </div>
          <n-form-item label="册内显示名">
            <n-input
              :value="templateDraft.title ?? ''"
              placeholder="留空使用模板原名"
              maxlength="40"
              @update:value="setTemplateTitle"
            />
          </n-form-item>
          <n-form-item label="标题级别">
            <n-select
              :value="templateDraft.heading_level"
              class="pb-editor-level"
              :options="LEVEL_OPTIONS"
              @update:value="setTemplateLevel"
            />
          </n-form-item>
          <n-form-item label="是否包含说明">
            <n-select
              :value="bodyMode(templateDraft)"
              :options="BODY_OPTIONS"
              class="pb-editor-level"
              @update:value="(v: string) => onBodyModeChange(v, templateDraft)"
            />
          </n-form-item>
        </template>

        <template v-else-if="markdownDraft">
          <n-form-item label="小标题">
            <n-input
              :value="markdownDraft.title ?? ''"
              placeholder="可选"
              maxlength="40"
              @update:value="setMarkdownTitle"
            />
          </n-form-item>
          <n-form-item label="正文（Markdown）">
            <n-input
              :value="markdownDraft.content"
              type="textarea"
              :rows="8"
              placeholder="支持 $公式$ 与 Markdown 语法"
              class="pb-editor-textarea"
              @update:value="setMarkdownContent"
            />
          </n-form-item>
        </template>

        <template v-else-if="imageDraft">
          <div class="pb-editor-image">
            <img
              v-if="imageDraft.src.startsWith('blob:')"
              :src="imageDraft.src"
              alt=""
              class="pb-editor-thumb"
            />
            <span v-else class="pb-editor-thumb pb-editor-thumb-empty">图片</span>
            <n-button size="small" secondary @click="replaceImage">
              <template #icon><Upload :size="14" /></template>
              更换图片
            </n-button>
          </div>
          <n-form-item label="说明文字">
            <n-input
              :value="imageDraft.caption ?? ''"
              placeholder="可选"
              maxlength="60"
              @update:value="setImageCaption"
            />
          </n-form-item>
          <n-form-item label="打印宽度">
            <n-input :value="imageDraft.width" class="pb-editor-width" @update:value="setImageWidth" />
          </n-form-item>
        </template>
      </n-form>
      <div class="modal-actions">
        <n-button size="small" quaternary @click="emit('update:show', false)">取消</n-button>
        <n-button size="small" type="primary" @click="save">保存</n-button>
      </div>
    </template>
    <input
      ref="imageInput"
      type="file"
      accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"
      hidden
      @change="onImagePicked"
    />
  </n-modal>
</template>

<style scoped>
.pb-editor-modal {
  --n-border-radius: 12px;
}

.pb-editor-level {
  width: 160px;
}

.pb-editor-width {
  width: 160px;
}

.pb-editor-textarea textarea {
  font-family: var(--font-mono) !important;
  font-size: 12.5px !important;
  line-height: 1.6 !important;
}

.pb-editor-template-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}

.pb-editor-template-name {
  font-size: 12.5px;
  font-weight: 650;
  color: var(--text);
}

.pb-editor-template-version,
.pb-editor-template-lang {
  font-family: var(--font-mono);
  font-size: 10.5px;
  padding: 1px 7px;
  border-radius: 99px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--muted);
}

.pb-editor-image {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.pb-editor-thumb {
  width: 72px;
  height: 48px;
  object-fit: cover;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}

.pb-editor-thumb-empty {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: var(--faint);
}
</style>
