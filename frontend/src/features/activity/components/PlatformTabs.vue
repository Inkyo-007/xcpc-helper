<script setup lang="ts">
/** 汇总 / 单平台分段切换器：汇总 + 已绑定平台（按绑定顺序去重）。 */

import { computed } from 'vue'
import { LayoutGrid } from 'lucide-vue-next'
import { platformName } from '@/features/activity/model/mock'
import type { PlatformScope } from '@/features/activity/store'
import type { BoundAccount, PlatformId } from '@/features/activity/types'

const props = defineProps<{
  modelValue: PlatformScope
  accounts: BoundAccount[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: PlatformScope]
}>()

const platforms = computed<PlatformId[]>(() => {
  const seen = new Set<PlatformId>()
  for (const acc of props.accounts) seen.add(acc.platform)
  return [...seen]
})
</script>

<template>
  <div class="platform-tabs" role="tablist">
    <button
      type="button"
      class="tab-chip"
      :class="{ active: modelValue === 'all' }"
      role="tab"
      :aria-selected="modelValue === 'all'"
      @click="emit('update:modelValue', 'all')"
    >
      <LayoutGrid :size="13" />
      汇总
    </button>
    <button
      v-for="p in platforms"
      :key="p"
      type="button"
      class="tab-chip"
      :class="{ active: modelValue === p }"
      role="tab"
      :aria-selected="modelValue === p"
      @click="emit('update:modelValue', p)"
    >
      {{ platformName(p) }}
    </button>
  </div>
</template>

<style scoped>
.platform-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: 99px;
  background: var(--surface);
}

.tab-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 14px;
  border: 0;
  border-radius: 99px;
  background: transparent;
  color: var(--muted);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.16s ease, color 0.16s ease, transform 0.16s ease;
}

.tab-chip:hover {
  background: var(--surface-2);
  color: var(--text);
}

.tab-chip.active {
  background: var(--accent-soft);
  color: var(--accent-strong);
  animation: chip-pop 0.3s cubic-bezier(0.2, 0.8, 0.3, 1.2);
}
</style>
