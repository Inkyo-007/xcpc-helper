<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { EditorState } from '@codemirror/state'
import {
  drawSelection,
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { syntaxHighlighting } from '@codemirror/language'
import { cpp } from '@codemirror/lang-cpp'
import { xcpcHighlight, xcpcTheme } from '@/shared/utils/codemirror'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const host = ref<HTMLDivElement | null>(null)
let view: EditorView | null = null

onMounted(() => {
  if (!host.value) return
  view = new EditorView({
    parent: host.value,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        lineNumbers(),
        highlightActiveLineGutter(),
        highlightActiveLine(),
        drawSelection(),
        history(),
        keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
        EditorView.lineWrapping,
        xcpcTheme,
        syntaxHighlighting(xcpcHighlight),
        cpp(),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) emit('update:modelValue', update.state.doc.toString())
        }),
      ],
    }),
  })
})

// 外部赋值（如上传文件、切换表单）时同步进编辑器；
// 与当前内容一致时跳过，避免打断正在进行的输入
watch(
  () => props.modelValue,
  (value) => {
    if (!view || view.state.doc.toString() === value) return
    view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: value } })
  },
)

onBeforeUnmount(() => view?.destroy())
</script>

<template>
  <div ref="host" class="cm-editor-host"></div>
</template>

<style scoped>
.cm-editor-host {
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  max-height: 300px;
  overflow: hidden;
  transition: border-color 0.15s ease;
}

.cm-editor-host:focus-within {
  border-color: var(--accent);
}

.cm-editor-host :deep(.cm-editor) {
  max-height: 300px;
}

.cm-editor-host :deep(.cm-scroller) {
  overflow: auto;
}
</style>
