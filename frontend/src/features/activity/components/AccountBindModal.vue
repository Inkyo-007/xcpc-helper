<script setup lang="ts">
/** 绑定平台账号弹窗：顶部提示「你正在绑定 <平台> 账号」→ 验证回执 → 确认绑定。
 * 平台由入口锁定（平台视图账号按钮 / 编辑用户组弹窗逐行入口），弹窗内不再
 * 提供平台切换；空状态入口（platform 为 null）回落为平台列表首个，用户可
 * 先点平台页签再绑定以选择平台。
 *
 * cookie 授权平台（洛谷等，auth === 'cookie'）提供两种绑定方式：
 * · 方式一 · 一键登录（browserLogin 可用时，推荐）：后端拉起系统浏览器
 *   登录窗口，用户自行登录，本弹窗轮询会话状态，成功后直接给出回执
 *   （凭据由后端暂存，不经前端，确认绑定时消费）；
 * · 方式二 · 手动输入 cookie：按平台注册表逐字段引导输入（洛谷为 _uid
 *   与 __client_id；_uid 即平台 UID，兼作 API 主键 handle），配有
 *   「如何获取 cookie？」悬浮引导；验证时携带凭据（后端同时校验用户
 *   存在性与凭据有效性）。
 */

import { computed, ref, watch } from 'vue'
import { BadgeCheck, CircleHelp, Globe, Link2, Search } from 'lucide-vue-next'
import { NButton, NInput, NModal, NPopover } from 'naive-ui'
import { startBrowserLogin, fetchBrowserLoginStatus, verifyAccount } from '@/features/activity/api'
import { useActivity } from '@/features/activity/store'
import type { AccountCredentials, PlatformId } from '@/features/activity/types'

/** cookie 平台注册表（前端平台知识，与后端 adapter 对齐）：
 * keys 为需录入的 cookie 字段；handleKey 表示该字段值即平台 API 主键
 * （洛谷 _uid 即 UID），此时不再单独要求输入 handle。 */
const COOKIE_PLATFORMS: Partial<
  Record<PlatformId, { keys: { key: string; label: string }[]; handleKey?: string }>
> = {
  luogu: {
    keys: [
      { key: '_uid', label: '_uid（即洛谷 UID）' },
      { key: '__client_id', label: '__client_id' },
    ],
    handleKey: '_uid',
  },
  'leetcode-cn': {
    keys: [
      { key: 'LEETCODE_SESSION', label: 'LEETCODE_SESSION' },
      { key: 'csrftoken', label: 'csrftoken' },
    ],
  },
}

const props = defineProps<{
  show: boolean
  /** 入口锁定的平台；null（空状态入口）回落为平台列表首个 */
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

const platform = ref<PlatformId>(props.platform ?? platforms.value[0]?.id ?? 'codeforces')
const handle = ref('')
const verifying = ref(false)
const errorText = ref('')
/** 验证成功的回执（真实接口返回的平台内用户信息） */
const receipt = ref<{ handle: string; displayName: string | null; avatar: string | null } | null>(null)
/** 回执来源为一键登录时，凭据由后端暂存，bind 不再携带 credentials */
const receiptFromLogin = ref(false)

/** cookie 平台逐字段输入值（键即 cookie 名） */
const cookieValues = ref<Record<string, string>>({})
/** 一键登录等待中（后端登录窗口打开，轮询会话状态） */
const loginWaiting = ref(false)

/** 当前所选平台是否已有绑定账号：有则本次为换绑 */
const rebinding = computed(() => boundOn(platform.value) !== null)

/** 当前平台的 cookie 注册表项（非 cookie 平台为 null） */
const cookieSpec = computed(() => COOKIE_PLATFORMS[platform.value] ?? null)
const isCookiePlatform = computed(
  () => platformMeta(platform.value)?.auth === 'cookie' && cookieSpec.value !== null,
)
/** 一键登录可用（后端具备浏览器登录能力） */
const canBrowserLogin = computed(
  () => isCookiePlatform.value && platformMeta(platform.value)?.browserLogin === true,
)
/** handle 由某个 cookie 字段兼任时（洛谷 _uid），不单独显示 handle 输入 */
const handleFromCookie = computed(() => cookieSpec.value?.handleKey ?? null)

/** 匿名平台输入框占位符 */
const handlePlaceholder = computed(() => {
  if (platform.value === 'nowcoder') return '输入账号 UID'
  if (platform.value === 'vjudge') return '输入 VJudge 用户名'
  return '输入平台用户名'
})

/** 手动输入的凭据（逐字段齐全时给出） */
const parsedCredentials = computed<AccountCredentials | null>(() => {
  const spec = cookieSpec.value
  if (!spec) return null
  const cookies: Record<string, string> = {}
  for (const { key } of spec.keys) {
    const value = cookieValues.value[key]?.trim()
    if (!value) return null
    cookies[key] = value
  }
  return { cookies }
})

/** 实际参与验证/绑定的 handle：cookie 兼任时取对应字段值，否则需要用户手动输入 handle */
const effectiveHandle = computed(() => {
  if (handleFromCookie.value) return (cookieValues.value[handleFromCookie.value] ?? '').trim()
  // LeetCode CN 等非 handleKey 平台：用户需手动输入 handle（userSlug）
  return handle.value.trim()
})

/** 当前是否为需要手动输入 handle 的 cookie 平台（无 handleKey） */
const needsManualHandle = computed(() => isCookiePlatform.value && !handleFromCookie.value)

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
      cookieValues.value = {}
      loginWaiting.value = false
    }
  },
)

watch([platform, handle, cookieValues], () => {
  errorText.value = ''
  receipt.value = null
  receiptFromLogin.value = false
}, { deep: true })

const canVerify = computed(() => {
  if (verifying.value || loginWaiting.value) return false
  if (!effectiveHandle.value) return false
  // cookie 平台手动路径：逐字段填齐才可验证
  if (isCookiePlatform.value) return parsedCredentials.value !== null
  return true
})

async function verify(): Promise<void> {
  const name = effectiveHandle.value
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
        // 注意：不要回填 handle 输入框——watcher 会把程序化赋值误判为
        // 用户改动而清空回执（曾致"登录成功却无反馈、无法绑定"）
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
        errorText.value = status.error ?? '登录失败，请改用方式二手动输入'
        return
      }
      await new Promise((r) => setTimeout(r, 1000))
    }
    errorText.value = '登录等待超时，请重试'
  } catch (e) {
    errorText.value = e instanceof Error ? e.message : '启动登录窗口失败，请改用方式二手动输入'
  } finally {
    loginWaiting.value = false
  }
}

function confirm(): void {
  if (!receipt.value) return
  emit('bind', platform.value, receipt.value.handle, {
    displayName: receipt.value.displayName,
    // 一键登录的凭据由后端暂存消费；手动输入路径携带逐字段凭据
    credentials: receiptFromLogin.value ? undefined : (parsedCredentials.value ?? undefined),
  })
  emit('update:show', false)
}

/** 回执展示名：优先 displayName（洛谷用户名），空回退 handle */
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
      <p class="bind-target">
        你正在{{ rebinding ? '换绑' : '绑定' }} <b>{{ platformName(platform) }}</b> 账号
      </p>

      <!-- 匿名平台：用户名 + 验证 -->
      <div v-if="!isCookiePlatform" class="bind-row">
        <n-input
          v-model:value="handle"
          size="small"
          :placeholder="handlePlaceholder"
          class="bind-handle"
          @keyup.enter="verify"
        />
        <n-button size="small" :loading="verifying" :disabled="!canVerify" @click="verify">
          <template #icon><Search :size="14" /></template>
          验证
        </n-button>
      </div>

      <!-- cookie 平台：两种方式（一键登录 / 手动输入 cookie） -->
      <template v-else>
        <template v-if="canBrowserLogin">
          <div class="bind-way-title">方式一 · 一键登录（推荐）</div>
          <n-button
            size="small"
            type="primary"
            secondary
            block
            :loading="loginWaiting"
            @click="browserLogin"
          >
            <template #icon><Globe :size="14" /></template>
            {{ loginWaiting ? '等待浏览器中登录…' : '打开浏览器登录' }}
          </n-button>
          <p class="bind-way-hint">在弹出的浏览器窗口中登录，完成后自动识别账号</p>
        </template>

        <div v-if="!canBrowserLogin" class="bind-way-title">手动输入 cookie</div>
        <div v-else class="bind-way-title">方式二 · 手动输入 cookie</div>
        <n-popover trigger="hover" :style="{ maxWidth: '340px' }">
          <template #trigger>
            <span class="cookie-help">
              <CircleHelp :size="13" />
              如何获取 cookie？
            </span>
          </template>
          <div class="cookie-guide">
            <template v-if="platform === 'leetcode-cn'">
              <p>1. 浏览器登录 LeetCode CN（leetcode.cn）</p>
              <p>2. 按 <code>F12</code> 打开开发者工具，切到「应用 / Application」面板</p>
              <p>3. 左侧展开 Cookies → <code>https://leetcode.cn</code></p>
              <p>4. 复制 <code>LEETCODE_SESSION</code> 与 <code>csrftoken</code> 的「值」填入下方输入框</p>
            </template>
            <template v-else>
              <p>1. 浏览器登录洛谷（luogu.com.cn）</p>
              <p>2. 按 <code>F12</code> 打开开发者工具，切到「应用 / Application」面板</p>
              <p>3. 左侧展开 Cookies → <code>https://www.luogu.com.cn</code></p>
              <p>4. 复制 <code>_uid</code> 与 <code>__client_id</code> 的「值」填入下方输入框</p>
            </template>
            <p class="cookie-guide-note">cookie 仅保存在本机（secrets.json），不会上传到任何地方</p>
          </div>
        </n-popover>
        <!-- 无 handleKey 的 cookie 平台（如 LeetCode CN）需要手动输入 handle -->
        <div v-if="needsManualHandle" class="cookie-field">
          <span class="cookie-label mono">用户名</span>
          <n-input
            v-model:value="handle"
            size="small"
            placeholder="输入 LeetCode CN 账号 UID"
            class="mono"
            @keyup.enter="verify"
          />
        </div>
        <div v-for="field in cookieSpec!.keys" :key="field.key" class="cookie-field">
          <span class="cookie-label mono">{{ field.label }}</span>
          <n-input
            v-model:value="cookieValues[field.key]"
            size="small"
            :placeholder="`输入 ${field.key} 的值`"
            class="mono"
            @keyup.enter="verify"
          />
        </div>
        <div class="bind-row">
          <n-button size="small" :loading="verifying" :disabled="!canVerify" @click="verify">
            <template #icon><Search :size="14" /></template>
            验证
          </n-button>
          <span class="bind-way-hint">填齐上方字段后可验证</span>
        </div>
      </template>

      <p v-if="errorText" class="bind-error">{{ errorText }}</p>
      <div v-if="receipt" class="bind-receipt">
        <span class="receipt-avatar">{{ receiptLabel.slice(0, 1).toUpperCase() }}</span>
        <div class="receipt-body">
          <div class="receipt-handle mono">{{ receiptLabel }}</div>
          <div class="receipt-meta mono">
            {{ platformName(platform) }} 账号验证通过<template v-if="receipt.displayName && platform !== 'nowcoder'">（UID {{ receipt.handle }}）</template>
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

.bind-target {
  margin: 0;
  font-size: 12.5px;
  color: var(--muted);
}

.bind-target b {
  color: var(--text);
}

.bind-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.bind-handle {
  flex: 1;
  min-width: 0;
}

.bind-way-title {
  margin-top: 4px;
  font-size: 12px;
  font-weight: 700;
  color: var(--muted);
  letter-spacing: 0.02em;
}

.bind-way-hint {
  margin: 0;
  font-size: 11.5px;
  color: var(--faint);
}

.cookie-help {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  align-self: flex-start;
  font-size: 11.5px;
  color: var(--muted);
  cursor: help;
  border-bottom: 1px dashed var(--border);
  padding-bottom: 1px;
}

.cookie-help:hover {
  color: var(--accent-strong);
  border-bottom-color: var(--accent);
}

.cookie-guide {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  line-height: 1.5;
}

.cookie-guide p {
  margin: 0;
}

.cookie-guide code {
  padding: 0 4px;
  border-radius: 4px;
  background: var(--surface-2);
  font-size: 11px;
}

.cookie-guide-note {
  color: var(--faint);
  font-size: 11.5px;
}

.cookie-field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.cookie-label {
  width: 150px;
  flex: none;
  font-size: 11.5px;
  color: var(--muted);
  text-align: right;
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
