import { ref, watch } from 'vue'
import { TEMPLATES } from '@/data/templates'
import type { NewTemplateInput, Template } from '@/types'
import { load, save } from '@/utils/storage'

const KEY = 'xc-templates-v3'
const LEGACY_KEY = 'xc-templates-v2'

function withPriority(list: Template[]): Template[] {
  return list.map((template) => {
    if (typeof template.priority === 'number') return template
    const seed = TEMPLATES.find((item) => item.id === template.id)
    return { ...template, priority: seed?.priority ?? 0 }
  })
}

function loadTemplates(): Template[] {
  const current = load<Template[] | null>(KEY, null)
  if (current) return withPriority(current)
  const legacy = load<Template[] | null>(LEGACY_KEY, null)
  return legacy ? withPriority(legacy) : TEMPLATES
}

export function useTemplates() {
  const templates = ref<Template[]>(loadTemplates())

  watch(
    templates,
    (value) => {
      save(KEY, value)
    },
    { deep: true },
  )

  function addTemplate(input: NewTemplateInput): void {
    const nextId = templates.value.reduce((max, t) => Math.max(max, t.id), 0) + 1
    const slug =
      input.name
        .toLowerCase()
        .replace(/[^\w\u4e00-\u9fa5]+/g, '_')
        .replace(/^_+|_+$/g, '') || `template_${nextId}`

    templates.value.unshift({
      id: nextId,
      name: input.name,
      cat: input.cat,
      lang: input.lang,
      file: `${slug}.${input.lang === 'py' ? 'py' : input.lang === 'java' ? 'java' : 'cpp'}`,
      cplx: input.cplx || '未标注',
      tags: [],
      src: input.src || '本地新建',
      updated: new Date().toISOString().slice(0, 10),
      priority: input.priority ?? 0,
      desc: input.desc || '暂无说明',
      code: input.code,
      lastUsedAt: null,
    })
  }

  return {
    templates,
    addTemplate,
  }
}
