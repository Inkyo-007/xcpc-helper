<script setup lang="ts">
/** AI 分析报告卡片：渲染后端生成的 markdown 报告（LLM 或规则化降级）。
 *  头部带来源状态标签；source === 'rule' 且 note 非空时在正文顶部显示降级提示条。 */

import { computed } from 'vue'
import MarkdownView from '@/shared/components/MarkdownView.vue'
import type { AnalysisReportData } from '@/features/activity/types'

const props = defineProps<{
  data: AnalysisReportData | null
  loading: boolean
}>()

const statusLabel = computed(() => {
  const d = props.data
  if (!d) return ''
  return d.source === 'llm' ? `AI · ${d.model ?? 'LLM'}` : '规则化报告'
})
</script>

<template>
  <div class="report-card">
    <header class="rc-head">
      <span class="card-title">AI 分析报告</span>
      <span
        v-if="data"
        class="rc-tag"
        :class="data.source === 'llm' ? 'rc-tag-llm' : 'rc-tag-rule'"
      >
        {{ statusLabel }}
      </span>
    </header>

    <div v-if="data" class="rc-body">
      <p v-if="data.source === 'rule' && data.note" class="rc-note">{{ data.note }}</p>
      <MarkdownView :content="data.content" />
    </div>

    <div v-else class="rc-empty">
      {{ loading ? '正在生成 AI 报告…' : '点击“生成 AI 报告”查看你的训练诊断' }}
    </div>
  </div>
</template>

<style scoped>
.report-card {
  min-width: 0;
}

.rc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.rc-tag {
  flex: none;
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1;
  padding: 3px 8px;
  border-radius: 99px;
  border: 1px solid var(--border);
  white-space: nowrap;
}

.rc-tag-llm {
  background: var(--accent-soft);
  border-color: var(--accent);
  color: var(--accent-strong);
}

.rc-tag-rule {
  background: var(--surface-2);
  color: var(--muted);
}

.rc-body {
  min-width: 0;
}

.rc-note {
  margin: 0 0 10px;
  padding: 7px 10px;
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--muted);
  font-size: 12px;
  line-height: 1.55;
}

.rc-empty {
  padding: 14px 2px;
  color: var(--faint);
  font-size: 13px;
}

/* 报告正文基础排版：配色随主题变量，不写死颜色 */
.rc-body :deep(.md-view) {
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--text);
  word-break: break-word;
}

.rc-body :deep(.md-view) > :first-child {
  margin-top: 0;
}

.rc-body :deep(.md-view) > :last-child {
  margin-bottom: 0;
}

.rc-body :deep(.md-view) p {
  margin: 0 0 10px;
}

.rc-body :deep(.md-view) h1,
.rc-body :deep(.md-view) h2,
.rc-body :deep(.md-view) h3,
.rc-body :deep(.md-view) h4,
.rc-body :deep(.md-view) h5,
.rc-body :deep(.md-view) h6 {
  margin: 16px 0 8px;
  line-height: 1.35;
  font-weight: 700;
  color: var(--text);
}

.rc-body :deep(.md-view) h1 {
  font-size: 16px;
}

.rc-body :deep(.md-view) h2 {
  font-size: 15px;
}

.rc-body :deep(.md-view) h3 {
  font-size: 14px;
}

.rc-body :deep(.md-view) h4 {
  font-size: 13.5px;
}

.rc-body :deep(.md-view) h5,
.rc-body :deep(.md-view) h6 {
  font-size: 13px;
  color: var(--muted);
}

.rc-body :deep(.md-view) ul,
.rc-body :deep(.md-view) ol {
  margin: 0 0 10px;
  padding-left: 20px;
}

.rc-body :deep(.md-view) li {
  margin: 0 0 4px;
}

.rc-body :deep(.md-view) code {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0 4px;
}

.rc-body :deep(.md-view) pre {
  margin: 0 0 12px;
  padding: 10px 12px;
  background: var(--code-bg);
  border: 1px solid var(--code-border);
  border-radius: var(--radius-sm);
  overflow-x: auto;
  font-size: 12.5px;
  line-height: 1.6;
}

.rc-body :deep(.md-view) pre code {
  background: none;
  border: 0;
  padding: 0;
  color: var(--code-text);
}

.rc-body :deep(.md-view) blockquote {
  margin: 0 0 12px;
  padding: 2px 12px;
  border-left: 3px solid var(--border-strong);
  color: var(--muted);
}

.rc-body :deep(.md-view) table {
  border-collapse: collapse;
  margin: 0 0 12px;
  width: 100%;
  font-size: 12.5px;
}

.rc-body :deep(.md-view) th,
.rc-body :deep(.md-view) td {
  border: 1px solid var(--border);
  padding: 6px 10px;
  text-align: left;
}

.rc-body :deep(.md-view) th {
  background: var(--surface-2);
}

.rc-body :deep(.md-view) hr {
  border: 0;
  border-top: 1px solid var(--border);
  margin: 16px 0;
}

.rc-body :deep(.md-view) a {
  color: var(--accent-strong);
  text-decoration: none;
}

.rc-body :deep(.md-view) img {
  max-width: 100%;
}
</style>
