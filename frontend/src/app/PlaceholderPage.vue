<script setup lang="ts">
import { BookOpen, FileUp, Settings, Timer } from 'lucide-vue-next'
import type { PageId, PlaceholderMeta } from '@/types'

defineProps<{
  page: Exclude<PageId, 'lib'>
  meta: PlaceholderMeta
}>()

const iconMap = {
  book: BookOpen,
  import: FileUp,
  timer: Timer,
  settings: Settings,
}
</script>

<template>
  <div class="placeholder-page">
    <div class="ph-icon">
      <component :is="iconMap[meta.icon]" :size="27" />
    </div>
    <h2 class="ph-title">{{ meta.title }}</h2>
    <p class="ph-hint">{{ meta.hint }}</p>
    <span class="ph-milestone">M2 里程碑规划中</span>
  </div>
</template>
