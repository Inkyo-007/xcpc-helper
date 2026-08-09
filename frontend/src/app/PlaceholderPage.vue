<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { BookOpen, Settings, Timer } from 'lucide-vue-next'

const route = useRoute()
const meta = computed(() => route.meta.placeholder)

const iconMap = {
  book: BookOpen,
  timer: Timer,
  settings: Settings,
}
</script>

<template>
  <div v-if="meta" class="placeholder-page">
    <div class="ph-icon">
      <component :is="iconMap[meta.icon]" :size="27" />
    </div>
    <h2 class="ph-title">{{ meta.title }}</h2>
    <p class="ph-hint">{{ meta.hint }}</p>
    <span class="ph-milestone">M2 里程碑规划中</span>
  </div>
</template>
