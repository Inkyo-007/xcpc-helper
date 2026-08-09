<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Download, Upload } from 'lucide-vue-next'
import {
  NAlert,
  NButton,
  NModal,
  NRadio,
  NRadioGroup,
  NSpin,
  useMessage,
} from 'naive-ui'
import {
  analyzeBooksArchive,
  applyBooksImport,
  downloadAllBooksArchive,
  downloadBookArchive,
} from '@/features/transfer/api'
import TransferReport from '@/features/transfer/components/TransferReport.vue'
import TransferUpload from '@/features/transfer/components/TransferUpload.vue'
import type {
  BookAnalyzeResult,
  ConflictStrategy,
  ImportReport,
} from '@/features/transfer/types'

const props = defineProps<{
  show: boolean
  /** 当前册名（"导出当前册"选项），无选中册时为 null */
  activeName: string | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  /** 导入成功，携带实际落盘的册名（created + renamed.target + overwritten） */
  imported: [names: string[]]
}>()

const message = useMessage()

type Step = 'menu' | 'import-upload' | 'import-result' | 'import-report' | 'export-confirm'

const step = ref<Step>('menu')
const analyzing = ref(false)
const applying = ref(false)
const analysis = ref<BookAnalyzeResult | null>(null)
const strategy = ref<ConflictStrategy>('skip')
const report = ref<ImportReport | null>(null)
const errorMessage = ref('')
const exportScope = ref<'current' | 'all'>('current')

const title = computed(() => {
  switch (step.value) {
    case 'import-upload':
    case 'import-result':
    case 'import-report':
      return '导入打印册'
    case 'export-confirm':
      return '导出打印册'
    default:
      return '导入 / 导出'
  }
})

watch(
  () => props.show,
  (show) => {
    if (show) {
      step.value = 'menu'
      analysis.value = null
      report.value = null
      strategy.value = 'skip'
      errorMessage.value = ''
      exportScope.value = props.activeName ? 'current' : 'all'
    }
  },
)

function close(): void {
  emit('update:show', false)
}

async function onFile(file: File): Promise<void> {
  analyzing.value = true
  errorMessage.value = ''
  try {
    analysis.value = await analyzeBooksArchive(file)
    step.value = 'import-result'
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : '压缩包解析失败，请重试'
  } finally {
    analyzing.value = false
  }
}

async function confirmImport(): Promise<void> {
  if (!analysis.value) return
  applying.value = true
  try {
    report.value = await applyBooksImport(analysis.value.staging_id, strategy.value)
    step.value = 'import-report'
    const names = [
      ...report.value.created,
      ...report.value.overwritten,
      ...report.value.renamed.map((r) => r.target),
    ]
    emit('imported', names)
  } catch (err) {
    message.error(err instanceof Error ? err.message : '导入失败，请重试')
  } finally {
    applying.value = false
  }
}

function confirmExport(): void {
  if (exportScope.value === 'current' && props.activeName) {
    downloadBookArchive(props.activeName)
    message.success(`打印册「${props.activeName}」已开始下载`)
  } else {
    downloadAllBooksArchive()
    message.success('全部打印册归档已开始下载')
  }
  close()
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="title"
    :style="{ width: 'min(560px, calc(100vw - 40px))' }"
    @update:show="emit('update:show', $event)"
  >
    <!-- 模式选择 -->
    <div v-if="step === 'menu'" class="transfer-menu">
      <button type="button" class="transfer-option" @click="step = 'import-upload'">
        <Upload :size="18" class="transfer-option-icon" />
        <span class="transfer-option-body">
          <span class="transfer-option-title">导入打印册</span>
          <span class="transfer-option-desc">从本软件导出的册归档 zip 恢复打印册</span>
        </span>
      </button>
      <button type="button" class="transfer-option" @click="step = 'export-confirm'">
        <Download :size="18" class="transfer-option-icon" />
        <span class="transfer-option-body">
          <span class="transfer-option-title">导出打印册</span>
          <span class="transfer-option-desc">导出当前册或全部册配置（含图片资源）</span>
        </span>
      </button>
    </div>

    <!-- 导入：上传 -->
    <div v-else-if="step === 'import-upload'" class="transfer-step">
      <n-spin :show="analyzing">
        <TransferUpload
          hint="仅支持本软件导出的打印册归档 zip"
          :loading="analyzing"
          @select="onFile"
        />
      </n-spin>
      <n-alert v-if="errorMessage" type="error" :bordered="false">
        {{ errorMessage }}
      </n-alert>
      <div class="modal-actions">
        <n-button @click="step = 'menu'">返回</n-button>
      </div>
    </div>

    <!-- 导入：分析结果 -->
    <div v-else-if="step === 'import-result' && analysis" class="transfer-step">
      <n-alert type="success" :bordered="false">
        识别出 {{ analysis.books.length }} 本打印册
      </n-alert>
      <div class="analysis-list">
        <div v-for="book in analysis.books" :key="book.name" class="analysis-item">
          <span>{{ book.name }}</span>
          <span v-if="book.title !== book.name" class="analysis-note">{{ book.title }}</span>
        </div>
      </div>
      <n-alert v-if="analysis.warnings.length" type="warning" :bordered="false">
        <div>{{ analysis.warnings.length }} 册存在问题，导入时将跳过：</div>
        <div v-for="(w, i) in analysis.warnings" :key="i" class="warning-line">
          {{ w.path }}：{{ w.message }}
        </div>
      </n-alert>
      <div v-if="analysis.conflicts.length" class="conflict-block">
        <n-alert type="warning" :bordered="false">
          与现有打印册重名：{{ analysis.conflicts.join('、') }}
        </n-alert>
        <n-radio-group v-model:value="strategy" class="strategy-group">
          <n-radio value="skip">跳过冲突项（保留现有打印册）</n-radio>
          <n-radio value="overwrite">用压缩包内容覆盖现有打印册</n-radio>
          <n-radio value="rename">自动重命名导入（两者都保留）</n-radio>
        </n-radio-group>
      </div>
      <div class="modal-actions">
        <n-button @click="step = 'import-upload'">重新选择</n-button>
        <n-button type="primary" :loading="applying" @click="confirmImport">
          {{ analysis.warnings.length ? '仍要导入' : '确认导入' }}
        </n-button>
      </div>
    </div>

    <!-- 导入：报告 -->
    <div v-else-if="step === 'import-report' && report" class="transfer-step">
      <TransferReport :report="report" />
      <div class="modal-actions">
        <n-button type="primary" @click="close">完成</n-button>
      </div>
    </div>

    <!-- 导出：确认 -->
    <div v-else class="transfer-step">
      <n-radio-group v-model:value="exportScope" class="strategy-group">
        <n-radio value="current" :disabled="!activeName">
          导出当前册{{ activeName ? `（${activeName}）` : '' }}
        </n-radio>
        <n-radio value="all">导出所有册</n-radio>
      </n-radio-group>
      <n-alert type="info" :bordered="false">
        册配置只记录模板引用，不包含模板内容；在另一台机器导入后，
        需配合模板库归档一起迁移才能完整还原。
      </n-alert>
      <div class="modal-actions">
        <n-button @click="step = 'menu'">返回</n-button>
        <n-button type="primary" @click="confirmExport">
          <template #icon><Download :size="14" /></template>
          导出
        </n-button>
      </div>
    </div>
  </n-modal>
</template>

<style scoped>
.transfer-menu {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.transfer-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.transfer-option:hover {
  border-color: var(--accent);
  background: var(--bg);
}

.transfer-option-icon {
  flex: none;
  color: var(--accent);
}

.transfer-option-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.transfer-option-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text);
}

.transfer-option-desc {
  font-size: 12px;
  color: var(--muted);
}

.transfer-step {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.analysis-list {
  max-height: 220px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 8px 12px;
}

.analysis-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12.5px;
  padding: 1px 0;
}

.analysis-note {
  font-size: 11.5px;
  color: var(--faint);
}

.warning-line {
  font-size: 12px;
  margin-top: 4px;
}

.conflict-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.strategy-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
