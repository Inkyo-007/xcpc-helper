<script setup lang="ts">
/**
 * 右栏预览：屏幕预览即真实分页产物（Paged.js），导出 PDF 只是把同一份
 * 页框 DOM 送去打印——一致性好由构造保证。
 * Paged.js 布局需要真实测量，因此分页在离屏沙盒（visibility 隐藏但有布局）
 * 中进行，成功后再把页框移入可视宿主；display:none 会导致布局测量失败。
 */

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { NButton, NSpin, NTooltip } from 'naive-ui'
import { AlertTriangle, BookOpen, FileDown, ZoomIn, ZoomOut } from 'lucide-vue-next'
import { useMessage } from 'naive-ui'
import BookFlowSource from '@/components/printbook/preview/BookFlowSource.vue'
import { buildDocument } from '@/printbook/document'
import { PaginationRun, PAGE_WIDTH_PX, type PaginationReport } from '@/printbook/pagination'
import { printPages } from '@/printbook/print'
import type { PrintBookDetail } from '@/types'

const props = defineProps<{
  detail: PrintBookDetail | null
}>()

const message = useMessage()

const docModel = computed(() =>
  props.detail
    ? buildDocument({
        cover: props.detail.cover,
        options: props.detail.options,
        blocks: props.detail.blocks,
      })
    : null,
)

const issues = computed(() => docModel.value?.issues ?? [])

/* ---------------- 分页调度 ---------------- */

type Status = 'idle' | 'rendering' | 'ready' | 'error'
const status = ref<Status>('idle')
const report = ref<PaginationReport | null>(null)
const errorText = ref('')

const farmEl = ref<HTMLElement | null>(null)
const pagesHost = ref<HTMLElement | null>(null)
const rootEl = ref<HTMLElement | null>(null)
const hasPages = ref(false)

let runSeq = 0
let timer = 0
let currentRun: PaginationRun | null = null
/** 分页运行串行化：Paged.js chunker 增量渲染，并发运行会在沙盒里交错产出 */
let running = false
let pendingRerun = false
/** 离屏分页沙盒（非 display:none，保证 Paged.js 可测量） */
let sandbox: HTMLElement | null = null

function ensureSandbox(): HTMLElement {
  if (!sandbox || !sandbox.isConnected) {
    sandbox = document.createElement('div')
    sandbox.className = 'pb-paginate-sandbox'
    sandbox.style.width = `${PAGE_WIDTH_PX}px`
    document.body.appendChild(sandbox)
  }
  return sandbox
}

/** 入口：同一时刻只允许一个分页运行，运行期间收到的请求合并为一次重跑。 */
async function runPagination(): Promise<void> {
  if (running) {
    pendingRerun = true
    return
  }
  running = true
  try {
    do {
      pendingRerun = false
      await executeRun()
    } while (pendingRerun)
  } finally {
    running = false
  }
}

async function executeRun(): Promise<void> {
  const seq = ++runSeq
  status.value = 'rendering'
  errorText.value = ''
  let run: PaginationRun | null = null

  try {
    const doc = docModel.value
    const farm = farmEl.value
    if (!doc || !farm) {
      status.value = 'idle'
      return
    }
    const host = ensureSandbox()
    // 清空上一轮残留，避免重复运行在同一沙盒里叠加页面
    host.replaceChildren()
    const html = farm.innerHTML.replaceAll('pbfl-', 'pb-')
    run = new PaginationRun()
    let result = await run.run(html, host)
    if (result.pageCount === 0) {
      // 封面始终存在，页数为 0 说明本次分页读到了空源（挂载期竞态）：
      // 丢弃产物并立即重试一次
      run.dispose()
      host.replaceChildren()
      run = new PaginationRun()
      result = await run.run(html, host)
    }
    if (result.pageCount === 0) {
      run.dispose()
      throw new Error('分页产物为空，已自动重试一次，请检查内容')
    }
    if (seq !== runSeq) {
      run.dispose()
      return
    }
    // 成功：把分页产物移入可视宿主，销毁上一次分页（含其页面与注入样式）
    const pagesArea = host.querySelector<HTMLElement>('.pagedjs_pages')
    if (!pagesArea || !pagesHost.value) {
      run.dispose()
      throw new Error('分页产物缺失')
    }
    currentRun?.dispose()
    currentRun = run
    pagesHost.value.replaceChildren(pagesArea)
    hasPages.value = true
    report.value = result
    errorText.value = ''
    if (result.blankPages.length > 0) {
      status.value = 'error'
      errorText.value = `检测到空白页（第 ${result.blankPages.join('、')} 页），请检查分页符位置`
    } else if (result.missingAnchors.length > 0) {
      status.value = 'error'
      errorText.value = '目录页码解析失败，请重试'
    } else if (result.wrongPageSize) {
      status.value = 'error'
      errorText.value = '页框尺寸异常（非 A4），已阻止导出'
    } else {
      status.value = 'ready'
    }
  } catch (err) {
    run?.dispose()
    if (seq !== runSeq) return
    status.value = 'error'
    errorText.value = err instanceof Error ? `排版失败：${err.message}` : '排版失败'
  }
}

function schedule(): void {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => {
    void runPagination()
  }, 350)
}

watch(
  () => [props.detail?.blocks, props.detail?.options, props.detail?.cover],
  () => schedule(),
  { deep: true },
)

watch(
  () => props.detail?.name,
  () => {
    // 换册：旧页面立即失效，立即重排
    window.clearTimeout(timer)
    void runPagination()
  },
)

/* ---------------- 缩放 ---------------- */

const viewport = ref<HTMLElement | null>(null)
const fitZoom = ref(0.6)
/** null=适应宽度 */
const manualZoom = ref<number | null>(null)

const effectiveZoom = computed(() => manualZoom.value ?? fitZoom.value)
const zoomPercent = computed(() => `${Math.round(effectiveZoom.value * 100)}%`)

function measureFit(): void {
  const el = viewport.value
  if (!el) return
  const usable = el.clientWidth - 16
  fitZoom.value = Math.min(1.2, Math.max(0.3, usable / PAGE_WIDTH_PX))
}

let resizeObserver: ResizeObserver | null = null

function zoomBy(delta: number): void {
  const next = Math.min(1.6, Math.max(0.3, effectiveZoom.value + delta))
  manualZoom.value = Math.round(next * 100) / 100
}

function resetZoom(): void {
  manualZoom.value = null
}

/* ---------------- 导出 ---------------- */

const exporting = ref(false)

/** TS 对 .value 的收窄会跨 await 保留，用函数边界读取最新状态。 */
function isReady(): boolean {
  return status.value === 'ready'
}

async function ensureFresh(): Promise<boolean> {
  window.clearTimeout(timer)
  if (isReady()) return true
  // 有排队在先的改动：立即重排一次
  await runPagination()
  return isReady()
}

async function exportPdf(): Promise<void> {
  if (exporting.value || !docModel.value) return
  exporting.value = true
  try {
    const ok = await ensureFresh()
    if (!ok) {
      message.error(errorText.value || '排版未就绪，无法导出')
      return
    }
    const pages = pagesHost.value?.querySelector<HTMLElement>('.pagedjs_pages')
    if (!pages) {
      message.error('未找到分页产物，请重试')
      return
    }
    printPages(pages, docModel.value?.coverTitle || '打印册')
  } finally {
    exporting.value = false
  }
}

/* ---------------- 生命周期 ---------------- */

/** 把逃逸到全局的异常（watcher、第三方库异步回调）显示到状态栏，避免静默失败。 */
function onGlobalFailure(event: Event): void {
  const raw =
    event instanceof PromiseRejectionEvent
      ? event.reason
      : event instanceof ErrorEvent
        ? event.error
        : null
  const text = raw instanceof Error ? raw.message : String(raw ?? event.type)
  // 已在渲染/出错状态时不覆盖更具体的信息
  if (status.value === 'ready') return
  status.value = 'error'
  errorText.value = `排版失败：${text}`
}

onMounted(() => {
  window.addEventListener('error', onGlobalFailure)
  window.addEventListener('unhandledrejection', onGlobalFailure)
  measureFit()
  if (viewport.value) {
    resizeObserver = new ResizeObserver(measureFit)
    resizeObserver.observe(viewport.value)
  }
  ensureSandbox()
  void nextTick(() => runPagination())
})

onBeforeUnmount(() => {
  window.removeEventListener('error', onGlobalFailure)
  window.removeEventListener('unhandledrejection', onGlobalFailure)
  window.clearTimeout(timer)
  runSeq += 1
  resizeObserver?.disconnect()
  currentRun?.dispose()
  currentRun = null
  sandbox?.remove()
  sandbox = null
})
</script>

<template>
  <div ref="rootEl" class="pb-preview">
    <div class="pb-preview-toolbar">
      <div class="pb-preview-status">
        <n-spin v-if="status === 'rendering'" :size="14" />
        <span v-if="status === 'rendering'" class="pb-status-text">排版中…</span>
        <template v-else-if="status === 'ready' && report">
          <span class="pb-status-text">共 {{ report.pageCount }} 页</span>
        </template>
        <span v-else-if="status === 'error'" class="pb-status-text pb-status-error">
          <AlertTriangle :size="13" /> {{ errorText }}
        </span>
      </div>

      <div class="pb-preview-actions">
        <n-tooltip>
          <template #trigger>
            <n-button quaternary circle size="small" @click="zoomBy(-0.1)">
              <template #icon><ZoomOut :size="15" /></template>
            </n-button>
          </template>
          缩小
        </n-tooltip>
        <n-tooltip>
          <template #trigger>
            <button type="button" class="pb-zoom-text mono" @click="resetZoom">
              {{ zoomPercent }}
            </button>
          </template>
          {{ manualZoom === null ? '当前为适应宽度，点击保持' : '点击恢复适应宽度' }}
        </n-tooltip>
        <n-tooltip>
          <template #trigger>
            <n-button quaternary circle size="small" @click="zoomBy(0.1)">
              <template #icon><ZoomIn :size="15" /></template>
            </n-button>
          </template>
          放大
        </n-tooltip>
        <n-button
          type="primary"
          size="small"
          :loading="exporting"
          :disabled="!detail || status === 'error'"
          @click="exportPdf"
        >
          <template #icon><FileDown :size="15" /></template>
          导出 PDF
        </n-button>
      </div>
    </div>

    <div v-if="issues.length > 0" class="pb-issues">
      <div
        v-for="issue in issues"
        :key="`${issue.blockIndex}-${issue.message}`"
        class="pb-issue"
        :class="`pb-issue-${issue.level}`"
      >
        <AlertTriangle :size="12" />
        <span>条目 {{ issue.blockIndex + 1 }}：{{ issue.message }}</span>
      </div>
    </div>

    <div ref="viewport" class="pb-pages-viewport">
      <div v-if="!detail" class="pb-preview-empty">
        <BookOpen :size="30" />
        <p>选择或新建一个打印册开始编排</p>
      </div>
      <div
        v-show="detail"
        class="pb-pages-zoom"
        :style="{ zoom: effectiveZoom }"
      >
        <div ref="pagesHost" class="pb-pages-host"></div>
      </div>
      <div v-if="detail && !hasPages && status === 'rendering'" class="pb-preview-loading">
        <n-spin :size="22" />
        <p>正在排版…</p>
      </div>
    </div>

    <!-- 渲染农场：隐藏，仅供序列化 -->
    <div v-if="docModel" ref="farmEl" class="pb-flow-farm" aria-hidden="true">
      <BookFlowSource :document="docModel" />
    </div>
  </div>
</template>

<style scoped>
.pb-preview {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.pb-preview-toolbar {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
}

.pb-preview-status {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.pb-status-text {
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pb-status-error {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #d03050;
}

.pb-preview-actions {
  flex: none;
  display: flex;
  align-items: center;
  gap: 2px;
}

.pb-zoom-text {
  min-width: 44px;
  padding: 3px 4px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text);
  font-size: 12px;
  text-align: center;
  cursor: pointer;
  transition: background 0.15s ease;
}

.pb-zoom-text:hover {
  background: var(--surface-2);
}

.pb-issues {
  flex: none;
  max-height: 96px;
  overflow-y: auto;
  padding: 6px 10px;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.pb-issue {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
}

.pb-issue-error {
  color: #d03050;
}

.pb-issue-warning {
  color: #d48806;
}

.pb-pages-viewport {
  flex: 1;
  min-height: 0;
  overflow: auto;
  position: relative;
  background: var(--surface-2);
}

.pb-pages-zoom {
  width: max-content;
  min-width: 100%;
  margin: 0 auto;
}

.pb-preview-empty,
.pb-preview-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--faint);
  font-size: 13px;
}
</style>
