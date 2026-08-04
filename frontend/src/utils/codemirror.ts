/** CodeMirror 共享主题与高亮：只读预览（CodeView）与编辑器（CodeEditor）共用。 */

import { EditorView } from '@codemirror/view'
import { HighlightStyle } from '@codemirror/language'
import { tags } from '@lezer/highlight'

export const xcpcTheme = EditorView.theme({
  '&': {
    backgroundColor: 'transparent',
    color: 'var(--code-text)',
    fontSize: '13px',
  },
  '&.cm-focused': {
    outline: 'none',
  },
  '.cm-scroller': {
    fontFamily: 'var(--font-mono)',
    lineHeight: '1.7',
    overflow: 'hidden',
  },
  '.cm-content': {
    padding: '12px 0 20px',
    caretColor: 'var(--accent)',
  },
  '.cm-line': {
    padding: '0 16px 0 8px',
  },
  '.cm-gutters': {
    backgroundColor: 'transparent',
    border: 'none',
    color: 'var(--code-ln)',
    fontFamily: 'var(--font-mono)',
    fontSize: '11px',
  },
  '.cm-activeLine': {
    backgroundColor: 'rgb(255 255 255 / 0.035)',
  },
  '.cm-activeLineGutter': {
    backgroundColor: 'transparent',
    color: 'var(--accent)',
  },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': {
    backgroundColor: 'rgb(255 255 255 / 0.12)',
  },
  '&.cm-focused .cm-cursor': {
    borderLeftColor: 'var(--accent)',
  },
})

export const xcpcHighlight = HighlightStyle.define([
  { tag: tags.keyword, color: 'var(--code-kw)' },
  { tag: [tags.string, tags.special(tags.string)], color: 'var(--code-string)' },
  { tag: [tags.number, tags.bool, tags.null], color: 'var(--code-number)' },
  {
    tag: [tags.comment, tags.lineComment, tags.blockComment],
    color: 'var(--code-comment)',
    fontStyle: 'italic',
  },
  {
    tag: [tags.meta, tags.macroName, tags.definition(tags.macroName)],
    color: 'var(--code-preproc)',
  },
  { tag: [tags.typeName, tags.className, tags.namespace], color: '#86b8b1' },
  { tag: tags.function(tags.variableName), color: '#d8c37a' },
  { tag: tags.operator, color: '#c9b8a5' },
  { tag: tags.punctuation, color: '#8a8378' },
  { tag: tags.variableName, color: 'var(--code-text)' },
])
