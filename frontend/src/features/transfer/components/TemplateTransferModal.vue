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
  analyzeTemplatesArchive,
  applyTemplatesImport,
  downloadTemplatesArchive,
} from '@/features/transfer/api'
import TransferReport from '@/features/transfer/components/TransferReport.vue'
import TransferUpload from '@/features/transfer/components/TransferUpload.vue'
import { groupTemplatesByCategory } from '@/features/transfer/model/group'
import type {
  ConflictStrategy,
  ImportReport,
  TemplateAnalyzeResult,
} from '@/features/transfer/types'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  imported: []
}>()

const message = useMessage()

type Step = 'menu' | 'import-upload' | 'import-result' | 'import-report' | 'export-confirm'

const step = ref<Step>('menu')
const analyzing = ref(false)
const applying = ref(false)
const analysis = ref<TemplateAnalyzeResult | null>(null)
const strategy = ref<ConflictStrategy>('skip')
const report = ref<ImportReport | null>(null)
const errorMessage = ref('')

const groups = computed(() =>
  analysis.value ? groupTemplatesByCategory(analysis.value.templates) : [],
)

const title = computed(() => {
  switch (step.value) {
    case 'import-upload':
    case 'import-result':
    case 'import-report':
      return '导入模板'
    case 'export-confirm':
      return '导出模板库'
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
    analysis.value = await analyzeTemplatesArchive(file)
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
    report.value = await applyTemplatesImport(analysis.value.staging_id, strategy.value)
    step.value = 'import-report'
    emit('imported')
  } catch (err) {
    message.error(err instanceof Error ? err.message : '导入失败，请重试')
  } finally {
    applying.value = false
  }
}

function confirmExport(): void {
  downloadTemplatesArchive()
  message.success('模板库归档已开始下载')
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
          <span class="transfer-option-title">导入模板</span>
          <span class="transfer-option-desc">
            从 zip 压缩包导入：本软件归档或「分类/代码文件」平铺结构
          </span>
        </span>
      </button>
      <button type="button" class="transfer-option" @click="step = 'export-confirm'">
        <Download :size="18" class="transfer-option-icon" />
        <span class="transfer-option-body">
          <span class="transfer-option-title">导出模板库</span>
          <span class="transfer-option-desc">全库导出为标准结构 zip，用于备份与迁移</span>
        </span>
      </button>
    </div>

    <!-- 导入：上传 -->
    <div v-else-if="step === 'import-upload'" class="transfer-step">
      <n-spin :show="analyzing">
        <TransferUpload
          hint="支持本软件导出的归档，或「分类文件夹 + 平铺代码文件」的模板库"
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
        识别出 {{ analysis.category_count }} 个分类 / {{ analysis.template_count }} 个模板
        {{ analysis.kind === 'standard' ? '（本软件标准归档）' : '' }}
      </n-alert>
      <div class="analysis-list">
        <div v-for="group in groups" :key="group.category" class="analysis-group">
          <div class="analysis-category">{{ group.category }}</div>
          <div v-for="tpl in group.templates" :key="tpl.name" class="analysis-item">
            <span>{{ tpl.name }}</span>
            <span v-if="tpl.renamed_from" class="analysis-note">
              原名「{{ tpl.renamed_from }}」
            </span>
            <span class="analysis-note">
              {{ tpl.version_count ? `${tpl.version_count} 个版本` : '空模板' }}
            </span>
          </div>
        </div>
      </div>
      <n-alert v-if="analysis.warnings.length" type="warning" :bordered="false">
        <div>{{ analysis.warnings.length }} 处内容无法识别或不规范，导入时将跳过：</div>
        <div
          v-for="(w, i) in analysis.warnings"
          :key="i"
          class="warning-line"
        >
          {{ w.path }}：{{ w.message }}
        </div>
      </n-alert>
      <div v-if="analysis.conflicts.length" class="conflict-block">
        <n-alert type="warning" :bordered="false">
          与现有库存在 {{ analysis.conflicts.length }} 个同名模板：{{
            analysis.conflicts.join('、')
          }}
        </n-alert>
        <n-radio-group v-model:value="strategy" class="strategy-group">
          <n-radio value="skip">跳过冲突项（保留现有模板）</n-radio>
          <n-radio value="overwrite">用压缩包内容覆盖现有模板</n-radio>
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
      <n-alert type="info" :bordered="false">
        将导出当前模板库全部模板为 zip 归档。导出统一整理为
        「分类 / 模板 / 版本」三层标准结构，代码转为 UTF-8 编码，可直接用于备份与迁移。
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

.analysis-category {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  margin: 6px 0 2px;
}

.analysis-group:first-child .analysis-category {
  margin-top: 0;
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
