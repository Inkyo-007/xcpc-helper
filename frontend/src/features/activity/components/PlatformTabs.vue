<script setup lang="ts">
/** 汇总 / 单平台分段切换器：汇总 + 全部支持平台（来自后端平台注册表，
 * 与是否绑定无关；未绑定平台的视图用于引导绑定 / 换绑）。
 * 某平台账号同步中时，其页签文本右上角显示黄色圆点角标；
 * 凭据过期时显示红色圆点角标（不进入该平台页也可知悉；同步为后台属性，见 activity/conventions.md）。 */

import { computed } from 'vue'
import { LayoutGrid } from 'lucide-vue-next'
import { useActivity } from '@/features/activity/store'
import type { PlatformScope } from '@/features/activity/store'

defineProps<{
  modelValue: PlatformScope
}>()

const emit = defineEmits<{
  'update:modelValue': [value: PlatformScope]
}>()

const { platforms, accounts } = useActivity()

/** 正在同步的平台 id 集合（页签黄点角标） */
const syncingIds = computed(
  () => new Set(accounts.value.filter((a) => a.syncState === 'running').map((a) => a.platform)),
)

/** 凭据过期的平台 id 集合（页签红点角标） */
const authExpiredIds = computed(
  () => new Set(accounts.value.filter((a) => a.syncErrorCode === 'auth_expired').map((a) => a.platform)),
)
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
      :key="p.id"
      type="button"
      class="tab-chip"
      :class="{ active: modelValue === p.id }"
      role="tab"
      :aria-selected="modelValue === p.id"
      @click="emit('update:modelValue', p.id)"
    >
      <span class="tab-label">
        {{ p.name }}
        <i v-if="authExpiredIds.has(p.id)" class="tab-dot tab-dot--error" title="凭据过期" />
        <i v-else-if="syncingIds.has(p.id)" class="tab-dot" title="正在同步" />
      </span>
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

.tab-label {
  position: relative;
  display: inline-flex;
  align-items: center;
}

/* 同步中角标：文本右上角黄色圆点，轻呼吸提示 */
.tab-dot {
  position: absolute;
  top: -3px;
  right: -8px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #eab308;
  box-shadow: 0 0 0 2px var(--surface);
  animation: dot-pulse 1.6s ease-in-out infinite;
}

/* 凭据过期角标：文本右上角红色圆点，常亮 */
.tab-dot--error {
  background: #c63b57;
  animation: none;
}

@keyframes dot-pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.45;
    transform: scale(0.8);
  }
}
</style>
