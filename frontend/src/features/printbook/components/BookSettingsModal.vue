<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { NButton, NForm, NFormItem, NInput, NModal, NSelect, NSwitch } from 'naive-ui'
import type { PrintBookCover, PrintBookDetail, PrintBookOptions } from '@/features/printbook/types'

const props = defineProps<{
  show: boolean
  book: PrintBookDetail | null
  headingLevel: number
  templateLevel: number
}>()

const emit = defineEmits<{
  'update:show': [show: boolean]
  save: [cover: PrintBookCover, options: PrintBookOptions, headingLevel: number, templateLevel: number]
}>()

const LEVEL_OPTIONS = [1, 2, 3, 4, 5, 6].map((level) => ({
  label: `H${level}`,
  value: level,
}))

const cover = reactive<PrintBookCover>({
  title: '',
  subtitle: null,
  author: null,
  logo: null,
})

const options = reactive<PrintBookOptions>({
  include_toc: true,
  include_meta: true,
  include_body: true,
  h1_page_break: true,
})

const headingLevel = ref(2)
const templateLevel = ref(3)

watch(
  () => props.show,
  (show) => {
    if (!show || !props.book) return
    Object.assign(cover, props.book.cover)
    Object.assign(options, props.book.options)
    headingLevel.value = props.headingLevel
    templateLevel.value = props.templateLevel
  },
)

function save(): void {
  emit('save', { ...cover }, { ...options }, headingLevel.value, templateLevel.value)
  emit('update:show', false)
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    class="create-modal pb-settings-modal"
    title="封面与选项"
    :style="{ width: '520px' }"
    @update:show="emit('update:show', $event)"
  >
    <n-form label-placement="top" size="small">
      <div class="pb-settings-section">封面</div>
      <n-form-item label="标题">
        <n-input v-model:value="cover.title" maxlength="40" />
      </n-form-item>
      <div class="pb-settings-grid">
        <n-form-item label="副标题">
          <n-input
            :value="cover.subtitle ?? ''"
            placeholder="可选"
            maxlength="40"
            @update:value="(v: string) => (cover.subtitle = v || null)"
          />
        </n-form-item>
        <n-form-item label="作者">
          <n-input
            :value="cover.author ?? ''"
            placeholder="可选"
            maxlength="30"
            @update:value="(v: string) => (cover.author = v || null)"
          />
        </n-form-item>
      </div>
      <n-form-item label="封面 Logo">
        <n-input
          :value="cover.logo ?? ''"
          placeholder="assets/ 相对路径，可选"
          @update:value="(v: string) => (cover.logo = v || null)"
        />
      </n-form-item>
      <div class="pb-settings-section">打印选项</div>
      <div class="pb-settings-switches">
        <div class="pb-settings-switch-row">
          <span class="pb-settings-label">生成目录</span>
          <n-switch v-model:value="options.include_toc" size="small" />
        </div>
        <div class="pb-settings-switch-row">
          <span class="pb-settings-label">显示元信息</span>
          <n-switch v-model:value="options.include_meta" size="small" />
        </div>
        <div class="pb-settings-switch-row">
          <span class="pb-settings-label">默认包含说明</span>
          <n-switch v-model:value="options.include_body" size="small" />
        </div>
        <div class="pb-settings-switch-row">
          <span class="pb-settings-label">一级标题前分页</span>
          <n-switch v-model:value="options.h1_page_break" size="small" />
        </div>
      </div>
      <div class="pb-settings-section">添加默认级别</div>
      <div class="pb-settings-levels">
        <div class="pb-settings-switch-row">
          <span class="pb-settings-label">标题级别</span>
          <n-select
            v-model:value="headingLevel"
            class="pb-settings-level-select"
            size="small"
            :options="LEVEL_OPTIONS"
          />
        </div>
        <div class="pb-settings-switch-row">
          <span class="pb-settings-label">模板节级别</span>
          <n-select
            v-model:value="templateLevel"
            class="pb-settings-level-select"
            size="small"
            :options="LEVEL_OPTIONS"
          />
        </div>
      </div>
    </n-form>
    <div class="modal-actions">
      <n-button size="small" quaternary @click="emit('update:show', false)">取消</n-button>
      <n-button size="small" type="primary" @click="save">保存</n-button>
    </div>
  </n-modal>
</template>

<style scoped>
.pb-settings-modal {
  --n-border-radius: 12px;
}

.pb-settings-section {
  margin: 4px 0 10px;
  font-size: 11.5px;
  font-weight: 700;
  color: var(--accent-strong);
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}

.pb-settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 14px;
}

.pb-settings-switches {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pb-settings-switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 36px;
  padding: 0 2px;
  border-bottom: 1px dashed var(--border);
}

.pb-settings-switch-row:last-child {
  border-bottom: 0;
}

.pb-settings-label {
  font-size: 12.5px;
  color: var(--text);
}

.pb-settings-level-select {
  width: 120px;
}
</style>
