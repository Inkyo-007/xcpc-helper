<script setup lang="ts">
import { computed } from 'vue'
import { NAlert } from 'naive-ui'
import type { ImportReport } from '@/features/transfer/types'

const props = defineProps<{
  report: ImportReport
}>()

const summary = computed(() => {
  const r = props.report
  const parts = [`新建 ${r.created.length}`]
  if (r.overwritten.length) parts.push(`覆盖 ${r.overwritten.length}`)
  if (r.renamed.length) parts.push(`自动重命名 ${r.renamed.length}`)
  if (r.skipped.length) parts.push(`跳过 ${r.skipped.length}`)
  if (r.failed.length) parts.push(`失败 ${r.failed.length}`)
  return parts.join('，')
})
</script>

<template>
  <div class="transfer-report">
    <n-alert :type="report.failed.length ? 'warning' : 'success'" :bordered="false">
      导入完成：{{ summary }}
    </n-alert>
    <div v-if="report.renamed.length" class="report-section">
      <div class="report-label">自动重命名</div>
      <div v-for="entry in report.renamed" :key="entry.source" class="report-line">
        {{ entry.source }} → {{ entry.target }}
      </div>
    </div>
    <div v-if="report.failed.length" class="report-section">
      <div class="report-label">失败明细</div>
      <div v-for="entry in report.failed" :key="entry.id" class="report-line report-failed">
        {{ entry.id }}：{{ entry.message }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.transfer-report {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.report-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.report-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
}

.report-line {
  font-size: 12.5px;
  color: var(--text);
  font-family: var(--font-mono);
}

.report-failed {
  color: #e5484d;
}
</style>
