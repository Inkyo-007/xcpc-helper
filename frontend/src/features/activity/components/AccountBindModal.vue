<script setup lang="ts">
/** 绑定平台账号弹窗：平台选择 → handle 输入 → 验证回执 → 确认绑定。
 * 从平台视图的账号按钮打开时锁定该平台；该平台已有账号时为换绑
 * （新账号替换旧账号及其本地数据，见 store.bindAccount）。
 * 平台下拉由后端平台注册表驱动。
 *
 * cookie 授权平台（洛古等，auth === 'cookie'）额外展开凭据区：
 * · 一键登录（browserLogin 可用时）：后端拉起系统浏览器登录窗口，
 *   用户自行登录，本弹窗轮询会话状态，成功后直接给出回执
 *   （凭据由后端暂存，不经前端，确认绑定时消费）；
 * · 手动粘贴：接受 JSON 或整串 Cookie 头（model/credentials.ts 解析），
 *   验证时携带凭据（后端同时校验用户存在性与凭据有效性）。
 */

import { computed, ref, watch } from 'vue'
import { BadgeCheck, Globe, Link2, Search } from 'lucide-vue-next'
import { NButton, NInput, NModal, NSelect } from 'naive-ui'
import { startBrowserLogin, fetchBrowserLoginStatus, verifyAccount } from '@/features/activity/api'
import { parseCredentialInput } from '@/features/activity/model/credentials'
import { useActivity } from '@/features/activity/store'
import type { AccountCredentials, PlatformId } from '@/features/activity/types'

/** cookie 平台所需的 cookie 字段（前端平台知识注册表，与后端 adapter 对齐） */
const COOKIE_KEYS: Partial<Record<PlatformId, string[]>> = {
  luogu: ['_uid', '__client_id'],
}

const props = defineProps<{
  show: boolean
  /** 从平台视图的账号按钮打开时锁定该平台；null 表示自由选择平台 */
  platform?: PlatformId | null
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  bind: [
    platform: PlatformId,
    handle: string,
    opts: { displayName?: string | null; credentials?: AccountCredentials },
  ]
}>()

const { platforms, platformName, platformMeta, isBound, boundOn } = useActivity()

const platformOptions = computed(() =>
  platforms.value.map((p) => ({ label: p.name, value: p.id })),
)

const platform = ref<PlatformId>(props.platform ?? 'codeforces')
const handle = ref('')
const verifying = ref(false)
const errorText = ref('')
/** 验证成功的回执（真实接口返回的平台内用户信息） */
const receipt = ref<{ handle: string; displayName: string | null; avatar: string | null } | null>(null)
/** 回执来源为一键登录时，凭据由后端暂存，bind 不再携带 credentials */
const receiptFromLogin = ref(false)

/** cookie 平台的手动粘贴输入 */
const cookieText = ref('')
/** 一键登录等待中（后端登录窗口打开，轮询会话状态） */
const loginWaiting = ref(false)

/** 锁定平台：从平台视图的账号按钮打开时不可切换平台 */
const platformLocked = computed(() => props.platform != null)

/** 当前所选平台是否已有绑定账号：有则本次为换绑 */
const rebinding = computed(() => boundOn(platform.value) !== null)

/** 当前平台是否 cookie 授权（洛古等） */
const isCookiePlatform = computed(() => platformMeta(platform.value)?.auth === 'cookie')
/** 当前平台一键登录可用（后端具备浏览器登录能力） */
const canBrowserLogin = computed(
  () => isCookiePlatform.value && platformMeta(platform.value)?.browserLogin === true,
)

/** 手动粘贴解析出的凭据（缺失字段时为 null） */
const parsedCredentials = computed<AccountCredentials | null>(() => {
  if (!isCookiePlatform.value) return null
  const keys = COOKIE_KEYS[platform.value] ?? []
  return parseCredentialInput(cookieText.value, keys)
})

watch(
  () => props.show,
  (show) => {
    if (show) {
      platform.value = props.platform ?? platforms.value[0]?.id ?? 'codeforces'
      handle.value = ''
      verifying.value = false
      errorText.value = ''
      receipt.value = null
      receiptFromLogin.value = false
      cookieText.value = ''
      loginWaiting.value = false
    }
  },
)

watch([platform, handle, cookieText], () => {
  errorText.value = ''
  receipt.value = null
  receiptFromLogin.value = false
})

const canVerify = computed(() => {
  if (verifying.value || loginWaiting.value) return false
  if (!handle.value.trim()) return false
  // cookie 平台手动路径：必须粘贴出完整凭据才可验证
  if (isCookiePlatform.value) return parsedCredentials.value !== null
  return true
})

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
    const res = await verifyAccount(
      platform.value,
      name,
      parsedCredentials.value ?? undefined,
    )
    receipt.value = { handle: res.handle, displayName: res.displayName, avatar: res.avatar }
  } catch (e) {
    errorText.value = e instanceof Error ? e.message : '验证失败，请稍后重试'
  } finally {
    verifying.value = false
  }
}

/** 一键登录：后端拉起系统浏览器登录窗口，轮询会话状态至结束 */
async function browserLogin(): Promise<void> {
  errorText.value = ''
  receipt.value = null
  loginWaiting.value = true
  try {
    await startBrowserLogin(platform.value)
    // 轮询至终态（后端会话超时 3 分钟，前端留足余量）
    const deadline = Date.now() + 200_000
    while (Date.now() < deadline) {
      const status = await fetchBrowserLoginStatus(platform.value)
      if (status.state === 'success' && status.handle) {
        receipt.value = {
          handle: status.handle,
          displayName: status.displayName,
          avatar: status.avatar,
        }
        receiptFromLogin.value = true
        handle.value = status.handle
        return
      }
      if (status.state === 'canceled') {
        errorText.value = '登录窗口已关闭，未完成登录'
        return
      }
      if (status.state === 'timeout') {
        errorText.value = '登录等待超时，请重试'
        return
      }
      if (status.state === 'error') {
        errorText.value = status.error ?? '登录失败，请改用手动粘贴 cookie'
        return
      }
      await new Promise((r) => setTimeout(r, 1000))
    }
    errorText.value = '登录等待超时，请重试'
  } catch (e) {
    errorText.value = e instanceof Error ? e.message : '启动登录窗口失败，请改用手动粘贴 cookie'
  } finally {
    loginWaiting.value = false
  }
}

function confirm(): void {
  if (!receipt.value) return
  emit('bind', platform.value, receipt.value.handle, {
    displayName: receipt.value.displayName,
    // 一键登录的凭据由后端暂存消费；手动粘贴路径携带解析出的凭据
    credentials: receiptFromLogin.value ? undefined : (parsedCredentials.value ?? undefined),
  })
  emit('update:show', false)
}

/** 回执展示名：优先 displayName（洛古用户名），空回退 handle */
const receiptLabel = computed(() =>
  receipt.value ? (receipt.value.displayName ?? receipt.value.handle) : '',
)
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    :title="rebinding ? '换绑平台账号' : '绑定平台账号'"
    class="create-modal"
    :style="{ width: 'min(460px, calc(100vw - 40px))' }"
    @update:show="emit('update:show', false)"
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
          :placeholder="isCookiePlatform ? '输入平台用户名或 UID' : '输入平台用户名'"
          class="bind-handle"
          @keyup.enter="verify"
        />
        <n-button
          v-if="!isCookiePlatform"
          size="small"
          :loading="verifying"
          :disabled="!canVerify"
          @click="verify"
        >
          <template #icon><Search :size="14" /></template>
          验证
        </n-button>
      </div>

      <!-- cookie 平台凭据区 -->
      <template v-if="isCookiePlatform">
        <div v-if="canBrowserLogin" class="bind-row">
          <n-button
            size="small"
            type="primary"
            secondary
            block
            :loading="loginWaiting"
            @click="browserLogin"
          >
            <template #icon><Globe :size="14" /></template>
            {{ loginWaiting ? '等待浏览器中登录…' : '一键登录（打开浏览器登录）' }}
          </n-button>
        </div>
        <n-input
          v-model:value="cookieText"
          type="textarea"
          size="small"
          :rows="2"
          placeholder="手动粘贴 cookie（整串 Cookie 头或 JSON），需包含 _uid 与 __client_id"
          class="bind-cookie"
        />
        <div class="bind-row">
          <n-button
            size="small"
            :loading="verifying"
            :disabled="!canVerify"
            @click="verify"
          >
            <template #icon><Search :size="14" /></template>
            验证
          </n-button>
          <span class="bind-cookie-hint">
            {{ parsedCredentials ? '已识别凭据字段' : '粘贴 cookie 后可验证' }}
          </span>
        </div>
      </template>

      <p v-if="errorText" class="bind-error">{{ errorText }}</p>
      <div v-if="receipt" class="bind-receipt">
        <span class="receipt-avatar">{{ receiptLabel.slice(0, 1).toUpperCase() }}</span>
        <div class="receipt-body">
          <div class="receipt-handle mono">{{ receiptLabel }}</div>
          <div class="receipt-meta mono">
            {{ platformName(platform) }} 账号验证通过<template v-if="receipt.displayName">（UID {{ receipt.handle }}）</template>
          </div>
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
  align-items: center;
}

.bind-platform {
  width: 138px;
  flex: none;
}

.bind-handle {
  flex: 1;
  min-width: 0;
}

.bind-cookie {
  font-family: var(--font-mono, monospace);
}

.bind-cookie-hint {
  font-size: 11.5px;
  color: var(--faint);
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
