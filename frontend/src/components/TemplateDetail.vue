<script setup lang="ts">
import { computed } from 'vue'
import { Marked } from 'marked'
import markedKatex from 'marked-katex-extension'
import 'katex/dist/katex.min.css'
import CodeView from '@/components/CodeView.vue'
import type { LangId, TemplateDetail, TemplateVariant } from '@/types'

const props = defineProps<{
  detail: TemplateDetail
  variant?: TemplateVariant | null
  categoryName: string
}>()

const code = computed(() => props.variant?.code ?? props.detail.variants[0]?.code ?? '')
const file = computed(() => props.variant?.file ?? props.detail.file)
const lang = computed<LangId>(() => props.variant?.lang ?? props.detail.lang)

// 说明框随版本切换显示对应版本的 README 正文；本地内容可信，直接渲染
const desc = computed(() => props.variant?.body ?? props.detail.desc)
// 支持 $...$ 行内公式与 $$...$$ 块级公式（KaTeX）
const marked = new Marked()
marked.use(markedKatex({ throwOnError: false }))
const descHtml = computed(() => (desc.value ? marked.parse(desc.value) : ''))
</script>

<template>
  <div class="detail">
    <div class="detail-head">
      <div class="detail-title-row">
        <h2 class="detail-title">{{ detail.name }}</h2>
        <span v-if="variant && detail.variant_count > 1" class="variant-badge">{{
          variant.name
        }}</span>
        <span v-for="tag in detail.tags" :key="tag" class="tag">{{ tag }}</span>
      </div>
      <div class="detail-meta">
        <span class="meta-item"><b>分类</b>{{ categoryName }}</span>
        <span v-if="detail.src" class="meta-item">
          <b>来源</b>
          <a
            v-if="detail.page"
            :href="detail.page"
            target="_blank"
            rel="noopener noreferrer"
            class="src-link"
            >{{ detail.src }}</a
          >
          <template v-else>{{ detail.src }}</template>
        </span>
        <span v-if="detail.updated" class="meta-item"><b>更新于</b>{{ detail.updated }}</span>
        <span class="meta-item priority"><b>优先级</b>{{ detail.priority }}</span>
      </div>
    </div>
    <CodeView :code="code" :file="file" :lang="lang" />
    <!-- eslint-disable-next-line vue/no-v-html -->
    <div v-if="descHtml" class="detail-desc" v-html="descHtml"></div>
  </div>
</template>

<style scoped>
.variant-badge {
  padding: 2px 8px;
  border: 1px solid var(--accent);
  border-radius: 6px;
  color: var(--accent);
  font-size: 12px;
  line-height: 1.6;
}

.src-link {
  color: var(--accent);
  text-decoration: none;
}

.src-link:hover {
  text-decoration: underline;
}

.detail-desc :deep(pre) {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 12px;
  overflow-x: auto;
}

.detail-desc :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.92em;
}

.detail-desc :deep(p) {
  margin: 0.4em 0;
}
</style>
