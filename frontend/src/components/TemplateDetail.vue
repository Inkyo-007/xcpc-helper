<script setup lang="ts">
import { computed } from 'vue'
import { categoryOf } from '@/data/categories'
import CodeView from '@/components/CodeView.vue'
import type { Template, TemplateVariant } from '@/types'

const props = defineProps<{
  template: Template
  variant?: TemplateVariant | null
}>()

const code = computed(() => props.variant?.code ?? props.template.code)
const file = computed(() => props.variant?.file ?? props.template.file)
const lang = computed(() => props.variant?.lang ?? props.template.lang)
</script>

<template>
  <div class="detail">
    <div class="detail-head">
      <div class="detail-title-row">
        <h2 class="detail-title">{{ template.name }}</h2>
        <span v-if="variant" class="tag">{{ variant.name }}</span>
        <span v-for="tag in template.tags" :key="tag" class="tag">{{ tag }}</span>
      </div>
      <div class="detail-meta">
        <span class="meta-item"><b>分类</b>{{ categoryOf(template.cat).name }}</span>
        <span class="meta-item"><b>来源</b>{{ template.src }}</span>
        <span class="meta-item"><b>更新于</b>{{ template.updated }}</span>
        <span class="meta-item priority"><b>优先级</b>{{ template.priority ?? 0 }}</span>
      </div>
    </div>
    <CodeView :code="code" :file="file" :lang="lang" />
    <div class="detail-desc">{{ template.desc }}</div>
  </div>
</template>
