<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Check, Copy } from 'lucide-vue-next'
import { EditorState } from '@codemirror/state'
import {
  drawSelection,
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from '@codemirror/view'
import { defaultKeymap, history, historyKeymap } from '@codemirror/commands'
import { syntaxHighlighting } from '@codemirror/language'
import { cpp } from '@codemirror/lang-cpp'
import type { LangId } from '@/shared/types'
import { xcpcHighlight, xcpcTheme } from '@/shared/utils/codemirror'

const props = defineProps<{
  code: string
  file: string
  lang: LangId
}>()

const host = ref<HTMLDivElement | null>(null)
const copied = ref(false)
const scanKey = ref(0)
const lines = computed(() => props.code.split('\n').length)
let view: EditorView | null = null
let copiedTimer = 0

function createEditor(code: string): void {
  view?.destroy()
  if (!host.value) return
  view = new EditorView({
    parent: host.value,
    state: EditorState.create({
      doc: code,
      extensions: [
        lineNumbers(),
        highlightActiveLineGutter(),
        highlightActiveLine(),
        drawSelection(),
        history(),
        keymap.of([...defaultKeymap, ...historyKeymap]),
        EditorState.readOnly.of(true),
        EditorView.editable.of(false),
        EditorView.lineWrapping,
        xcpcTheme,
        syntaxHighlighting(xcpcHighlight),
        cpp(),
      ],
    }),
  })
}

async function copy(): Promise<void> {
  try {
    await navigator.clipboard.writeText(props.code)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = props.code
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    textarea.remove()
  }
  copied.value = true
  window.clearTimeout(copiedTimer)
  copiedTimer = window.setTimeout(() => {
    copied.value = false
  }, 1600)
}

onMounted(() => createEditor(props.code))

watch(
  () => props.code,
  (code) => {
    createEditor(code)
    scanKey.value += 1
  },
)

onBeforeUnmount(() => {
  view?.destroy()
  window.clearTimeout(copiedTimer)
})

defineExpose({ copy })
</script>

<template>
  <div class="code-view">
    <div class="code-head">
      <div class="code-status">
        <span class="status-led" aria-hidden="true"></span>
        <span class="code-file">{{ file }}</span>
        <span class="code-lang">{{ lang }}</span>
        <span class="code-lines">{{ lines }} 行</span>
      </div>
      <button
        type="button"
        class="copy-btn"
        :class="{ copied }"
        @click="copy"
      >
        <Check v-if="copied" :size="13" />
        <Copy v-else :size="13" />
        {{ copied ? '已复制' : '复制' }}
      </button>
    </div>
    <div ref="host" class="cm-host"></div>
    <div :key="scanKey" class="scan-line" aria-hidden="true"></div>
  </div>
</template>
