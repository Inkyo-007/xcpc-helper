<script setup lang="ts">
/**
 * 渲染农场：把 BookDocument 渲染为静态 HTML（隐藏，仅供序列化给 Paged.js）。
 * 锚点 id 使用 pbfl- 前缀，序列化时统一改写为 pb- 前缀，
 * 避免与分页产物撞 id 导致目录页码解析错位。
 */

import { computed } from 'vue'
import MarkdownView from '@/shared/components/MarkdownView.vue'
import { highlightCode } from '@/shared/utils/highlight'
import type { BookDocument, DocSection, ImageSection, TemplateSection } from '@/features/printbook/model/document'

const props = defineProps<{
  document: BookDocument
}>()

const doc = computed(() => props.document)

function anchorId(anchor: string): string {
  return `pbfl-${anchor}`
}

function headingTag(level: number): string {
  const clamped = Math.min(6, Math.max(1, Math.round(level)))
  return `h${clamped}`
}

function headingClass(level: number): string {
  const clamped = Math.min(6, Math.max(1, Math.round(level)))
  return `pb-h pb-h${clamped}`
}

function tocClass(level: number): string {
  const clamped = Math.min(6, Math.max(1, Math.round(level)))
  return `pb-toc-entry pb-toc-l${clamped}`
}

function codeHtml(sec: TemplateSection): string {
  return highlightCode(sec.info.code, sec.info.lang).html
}

/** 图片地址统一为绝对 URL：DOMParser 文档无 base，相对路径会解析失败。 */
function imageSrc(src: string): string {
  if (/^(https?:|blob:|data:)/.test(src)) return src
  const path = src.startsWith('/') ? src : `/${src}`
  return `${window.location.origin}${path}`
}

function figureWidth(sec: ImageSection): string {
  const width = sec.width.trim()
  return width || '80%'
}

function isTemplate(sec: DocSection): sec is TemplateSection {
  return sec.kind === 'template'
}
</script>

<template>
  <div class="pb-doc">
    <!-- 封面（固定版式，命名页 cover：无页脚页码） -->
    <section class="pb-doc-cover">
      <img v-if="doc.logo" class="pb-cover-logo" :src="imageSrc(doc.logo)" alt="" />
      <h1 class="pb-cover-title">{{ doc.coverTitle }}</h1>
      <p v-if="doc.subtitle" class="pb-cover-subtitle">{{ doc.subtitle }}</p>
      <hr class="pb-cover-rule" />
      <p v-if="doc.author" class="pb-cover-author">{{ doc.author }}</p>
    </section>

    <!-- 目录：页码由 target-counter 在分页后回填 -->
    <nav v-if="doc.toc" class="pb-doc-toc">
      <h2 class="pb-toc-head">目录</h2>
      <p v-if="doc.toc.length === 0" class="pb-toc-empty">（暂无条目）</p>
      <ul v-else class="pb-toc-list">
        <li v-for="entry in doc.toc" :key="entry.anchor" :class="tocClass(entry.level)">
          <span class="pb-toc-title">{{ entry.title }}</span>
          <span class="pb-toc-dots"></span>
          <a class="pb-toc-pg" :href="`#${anchorId(entry.anchor)}`"></a>
        </li>
      </ul>
    </nav>

    <!-- 章节序列 -->
    <template v-for="sec in doc.sections" :key="sec.key">
      <component
        :is="headingTag(sec.level)"
        v-if="sec.kind === 'heading'"
        :id="anchorId(sec.anchor)"
        :class="[headingClass(sec.level), { 'pb-brk': sec.pageBreakBefore }]"
      >
        {{ sec.title }}
      </component>

      <section
        v-else-if="isTemplate(sec)"
        class="pb-doc-sec pb-doc-tpl"
        :class="{ 'pb-brk': sec.pageBreakBefore }"
      >
        <component
          :is="headingTag(sec.level)"
          :id="anchorId(sec.anchor)"
          :class="headingClass(sec.level)"
        >
          {{ sec.title }}
        </component>
        <div v-if="sec.meta" class="pb-meta">
          <span><b>分类</b>{{ sec.meta.cat }}</span>
          <span class="pb-meta-ver">{{ sec.meta.versionName }}</span>
          <span v-for="tag in sec.meta.tags" :key="tag" class="pb-meta-tag">{{ tag }}</span>
          <span v-if="sec.meta.src">
            <b>来源</b>
            <a v-if="sec.meta.page" :href="sec.meta.page">{{ sec.meta.src }}</a>
            <template v-else>{{ sec.meta.src }}</template>
          </span>
          <span v-if="sec.meta.updated"><b>更新</b>{{ sec.meta.updated }}</span>
          <span><b>优先级</b>{{ sec.meta.priority }}</span>
        </div>
        <!-- eslint-disable-next-line vue/no-v-html -->
        <div class="pb-code-wrap" v-html="codeHtml(sec)"></div>
        <MarkdownView v-if="sec.body" class="pb-body pb-md" :content="sec.body" />
      </section>

      <section
        v-else-if="sec.kind === 'markdown'"
        class="pb-doc-sec pb-doc-mdsec"
        :class="{ 'pb-brk': sec.pageBreakBefore }"
      >
        <h4 v-if="sec.title" class="pb-h pb-h4">{{ sec.title }}</h4>
        <MarkdownView class="pb-md" :content="sec.content" />
      </section>

      <figure
        v-else-if="sec.kind === 'image'"
        class="pb-fig"
        :class="{ 'pb-brk': sec.pageBreakBefore }"
      >
        <img :src="imageSrc(sec.src)" :alt="sec.caption ?? ''" :style="{ width: figureWidth(sec) }" />
        <figcaption v-if="sec.caption">{{ sec.caption }}</figcaption>
      </figure>
    </template>
  </div>
</template>
