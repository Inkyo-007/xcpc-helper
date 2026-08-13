<script setup lang="ts">
/** 绑定平台账号弹窗：平台选择 → handle 输入 → 验证回执 → 确认绑定。
 * 从平台视图的账号按钮打开时锁定该平台；该平台已有账号时为换绑
 * （新账号替换旧账号及其本地数据，见 store.bindAccount）。
 * 平台下拉由后端平台注册表驱动（第一期仅 Codeforces）。
 */

import { computed, ref, watch } from 'vue'
import { BadgeCheck, Link2, Search } from 'lucide-vue-next'
import { NButton, NInput, NModal, NSelect } from 'naive-ui'
import { verifyAccount } from '@/features/activity/api'
import { useActivity } from '@/features/activity/store'
import type { PlatformId } from '@/features/activity/types'

const props = defineProps<{
  show: boolean
  /** 从平台视图打开时锁定该平台；null 表示自由选择平台 */
  platform?: PlatformId | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  bind: [platform: PlatformId, handle: string]
}>()

const { platforms, platformName, isBound, boundOn } = useActivity()

const platformOptions = computed(() =>
  platforms.value.map((p) => ({ label: p.name, value: p.id })),
)

const platform = ref<PlatformId>(props.platform ?? 'codeforces')
const handle = ref('')
const verifying = ref(false)
const errorText = ref('')
/** 验证成功的回执（真实接口返回的平台内用户信息） */
const receipt = ref<{ handle: string; avatar: string | null } | null>(null)

/** 锁定平台：从平台视图的账号按钮打开时不可切换平台 */
const platformLocked = computed(() => props.platform != null)

/** 当前所选平台是否已有绑定账号：有则本次为换绑 */
const rebinding = computed(() => boundOn(platform.value) !== null)

watch(
  () => props.show,
  (show) => {
    if (show) {
      platform.value = props.platform ?? platforms.value[0]?.id ?? 'codeforces'
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
  try {
    const res = await verifyAccount(platform.value, name)
    receipt.value = { handle: res.handle, avatar: res.avatar }
  } catch (e) {
    errorText.value = e instanceof Error ? e.message : '验证失败，请稍后重试'
  } finally {
    verifying.value = false
  }
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
    :title="rebinding ? '换绑平台账号' : '绑定平台账号'"
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
          :disabled="platformLocked"
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
          <div class="receipt-meta mono">{{ platformName(platform) }} 账号验证通过</div>
        </div>
        <BadgeCheck class="receipt-check" :size="17" />
      </div>
    </div>
    <div class="modal-actions">
      <n-button size="small" quaternary @click="emit('update:show', false)">取消</n-button>
      <n-button size="small" type="primary" :disabled="!receipt" @click="confirm">
        <template #icon><Link2 :size="14" /></template>
        {{ rebinding ? '确认换绑' : '确认绑定' }}
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
