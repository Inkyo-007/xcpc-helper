<script setup lang="ts">
import { computed } from 'vue'
import { renderMarkdownCached } from '@/shared/utils/markdown'

const props = defineProps<{
  content: string
}>()

const html = computed(() => renderMarkdownCached(props.content))
</script>

<template>
  <!-- 本地内容可信，直接渲染；样式由使用方上下文提供（.detail-desc / .pb-md） -->
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="md-view" v-html="html"></div>
</template>
