<script setup lang="ts">
/** 绑定平台账号弹窗：平台选择 → handle 输入 → 验证回执 → 确认绑定。
 * mock 阶段：验证为模拟延迟 + 示例回执；后端就绪后替换为真实 verify 请求。
 */

import { computed, ref, watch } from 'vue'
import { BadgeCheck, Link2, Search } from 'lucide-vue-next'
import { NButton, NInput, NModal, NSelect } from 'naive-ui'
import { hashSeed, PLATFORMS } from '@/features/activity/model/mock'
import { useActivity } from '@/features/activity/store'
import type { PlatformId } from '@/features/activity/types'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  bind: [platform: PlatformId, handle: string]
}>()

const { isBound } = useActivity()

const platformOptions = PLATFORMS.map((p) => ({ label: p.name, value: p.id }))

const platform = ref<PlatformId>('codeforces')
const handle = ref('')
const verifying = ref(false)
const errorText = ref('')
/** 验证成功的回执（mock 示例数据） */
const receipt = ref<{ handle: string; rating: number } | null>(null)

watch(
  () => props.show,
  (show) => {
    if (show) {
      platform.value = 'codeforces'
      handle.value = ''
      verifying.value = false
      errorText.value = ''
      receipt.value = null
    }
  },
)

watch([platform, handle], () => {
  errorText.value = ''
  receipt.value = null
})

const canVerify = computed(() => handle.value.trim().length > 0 && !verifying.value)

async function verify(): Promise<void> {
  const name = handle.value.trim()
  if (!name) return
  if (isBound(platform.value, name)) {
    errorText.value = '该账号已绑定，无需重复添加'
    return
  }
  verifying.value = true
  errorText.value = ''
  await new Promise((r) => setTimeout(r, 700))
  verifying.value = false
  receipt.value = { handle: name, rating: 1300 + (hashSeed(name) % 900) }
}

function confirm(): void {
  if (!receipt.value) return
  emit('bind', platform.value, receipt.value.handle)
  emit('update:show', false)
}
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    title="绑定平台账号"
    class="create-modal"
    :style="{ width: 'min(460px, calc(100vw - 40px))' }"
    @update:show="emit('update:show', $event)"
  >
    <div class="bind-form">
      <div class="bind-row">
        <n-select
          v-model:value="platform"
          :options="platformOptions"
          size="small"
          class="bind-platform"
        />
        <n-input
          v-model:value="handle"
          size="small"
          placeholder="输入平台用户名"
          class="bind-handle"
          @keyup.enter="verify"
        />
        <n-button size="small" :loading="verifying" :disabled="!canVerify" @click="verify">
          <template #icon><Search :size="14" /></template>
          验证
        </n-button>
      </div>
      <p v-if="errorText" class="bind-error">{{ errorText }}</p>
      <div v-if="receipt" class="bind-receipt">
        <span class="receipt-avatar">{{ receipt.handle.slice(0, 1).toUpperCase() }}</span>
        <div class="receipt-body">
          <div class="receipt-handle mono">{{ receipt.handle }}</div>
          <div class="receipt-meta mono">rating {{ receipt.rating }} · 示例数据</div>
        </div>
        <BadgeCheck class="receipt-check" :size="17" />
      </div>
    </div>
    <div class="modal-actions">
      <n-button size="small" quaternary @click="emit('update:show', false)">取消</n-button>
      <n-button size="small" type="primary" :disabled="!receipt" @click="confirm">
        <template #icon><Link2 :size="14" /></template>
        确认绑定
      </n-button>
    </div>
  </n-modal>
</template>

<style scoped>
.bind-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bind-row {
  display: flex;
  gap: 8px;
}

.bind-platform {
  width: 138px;
  flex: none;
}

.bind-handle {
  flex: 1;
  min-width: 0;
}

.bind-error {
  margin: 0;
  font-size: 12.5px;
  font-weight: 600;
  color: #c63b57;
}

.bind-receipt {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--accent);
  border-radius: var(--radius);
  background: var(--accent-softer);
  animation: receipt-in 0.28s cubic-bezier(0.22, 0.8, 0.3, 1.1) both;
}

@keyframes receipt-in {
  from {
    opacity: 0;
    transform: translateY(6px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.receipt-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex: none;
  border-radius: 50%;
  background: var(--accent);
  color: var(--on-accent);
  font-weight: 700;
  font-size: 14px;
}

.receipt-body {
  min-width: 0;
}

.receipt-handle {
  font-size: 13px;
  font-weight: 700;
  color: var(--text);
}

.receipt-meta {
  font-size: 11px;
  color: var(--muted);
}

.receipt-check {
  margin-left: auto;
  flex: none;
  color: var(--accent-strong);
}
</style>
