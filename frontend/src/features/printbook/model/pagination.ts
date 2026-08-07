/**
 * Paged.js 分页引擎封装。
 *
 * 关键约束（历史问题复盘）：
 * - 必须显式传 stylesheets，否则 Paged.js 会把整个文档的样式表移除；
 * - 内容以 HTML 字符串传入（DOMParser 解析），不触碰应用 DOM；
 * - 分页前等待字体与图片就绪，否则页码与空白页都会算错；
 * - 每次运行生成独立 Previewer，其注入 head 的样式随 dispose 清理。
 *
 * 分页语义声明（break-before/break-after/page）必须随 PAGE_CSS 经 polisher 处理：
 * Paged.js 布局引擎只认 polisher 写入的 data-break-* / data-page 属性，
 * 文档中 paper.css 的同名声明（浏览器无法用于 JS 分页）不会生效。
 * 因此这里用 ?raw 注入同一份 paper.css，保证单一事实来源。
 */

import { Previewer } from 'pagedjs'
import paperCss from '@/shared/styles/paper.css?raw'

/** A4 = 210×297mm，内容区 = 180×267mm（边距 15mm）；封面无页脚页码。 */
export const PAGE_CSS = `
@page {
  size: A4;
  margin: 15mm;
  @bottom-right {
    content: counter(page);
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 11pt;
    font-weight: 700;
    color: #3d4451;
  }
}
@page cover {
  @bottom-right { content: none; }
}

/* 目录页码：target-counter 是非标准 CSS，浏览器直接忽略，
   必须放在这里交给 Paged.js polisher 解析并在分页后回填真实页码。
   （不要移到全局 paper.css，那里不会被 polisher 处理。） */
.pb-toc-pg::after {
  content: target-counter(attr(href url), page);
}

/* paper.css 原文（?raw 注入，单一事实来源）：
   - break-before / break-after / page: cover 会被 polisher 从 CSS 中移除，
     转为内容元素上的 data-* 属性驱动分页；
   - 其余视觉规则原样透传，与文档中的 paper.css 副本完全一致（无害重复）。 */
${paperCss}
`

/** A4 的 CSS 像素尺寸（96dpi：1mm ≈ 3.7795px） */
export const PAGE_WIDTH_PX = 793.7
export const PAGE_HEIGHT_PX = 1122.5

export interface PaginationReport {
  pageCount: number
  /** 无内容页框的页码（1 起） */
  blankPages: number[]
  /** 目录引用了但页面中不存在的锚点 */
  missingAnchors: string[]
  /** 页框尺寸异常（非 A4） */
  wrongPageSize: boolean
  performanceMs: number
}

function collectAnchors(html: string): string[] {
  const anchors: string[] = []
  const re = /id="(pb-sec-[^"]+)"/g
  let match: RegExpExecArray | null
  while ((match = re.exec(html)) !== null) anchors.push(match[1])
  return anchors
}

/** 等待字体与全部图片就绪（图片 URL 预热进缓存，分页副本瞬时加载）。 */
async function waitForAssets(html: string): Promise<void> {
  await document.fonts.ready
  const probe = document.createElement('div')
  probe.innerHTML = html
  const images = Array.from(probe.querySelectorAll('img'))
  await Promise.all(
    images.map(async (img) => {
      try {
        await img.decode()
      } catch {
        /* 缺失图片由渲染层的占位框与 issues 承担，不阻塞分页 */
      }
    }),
  )
}

function pageHasContent(page: HTMLElement): boolean {
  const area = page.querySelector('.pagedjs_page_content')
  if (!area) return false
  if ((area.textContent ?? '').trim().length > 0) return true
  // 图片等无文字内容也算有内容
  return area.querySelector('img, svg, table, .katex') !== null
}

export class PaginationRun {
  private previewer: Previewer | null = null
  private disposed = false

  async run(html: string, renderTo: HTMLElement): Promise<PaginationReport> {
    await waitForAssets(html)
    if (this.disposed) throw new Error('pagination run disposed')

    const previewer = new Previewer()
    this.previewer = previewer
    const flow = await previewer.preview(
      html,
      [{ 'https://printbook.local/paper.css': PAGE_CSS }],
      renderTo,
    )
    if (this.disposed) {
      this.disposeStyles()
      throw new Error('pagination run disposed')
    }

    const pages = Array.from(renderTo.querySelectorAll<HTMLElement>('.pagedjs_page'))
    const blankPages: number[] = []
    pages.forEach((page, index) => {
      if (!pageHasContent(page)) blankPages.push(index + 1)
    })

    const anchors = collectAnchors(html)
    const missingAnchors = anchors.filter((id) => !renderTo.querySelector(`#${id}`))

    let wrongPageSize = false
    const firstPage = pages[0]
    if (firstPage) {
      const rect = firstPage.getBoundingClientRect()
      // 屏幕缩放（zoom）会影响测量，按缩放比例折算回真实尺寸
      const zoom = Number(getComputedStyle(renderTo).zoom) || 1
      const width = rect.width / zoom
      const height = rect.height / zoom
      wrongPageSize =
        Math.abs(width - PAGE_WIDTH_PX) > 2 || Math.abs(height - PAGE_HEIGHT_PX) > 2
    }

    return {
      pageCount: pages.length || flow.total,
      blankPages,
      missingAnchors,
      wrongPageSize,
      performanceMs: flow.performance,
    }
  }

  private disposeStyles(): void {
    const polisher = this.previewer?.polisher
    // polisher.destroy() 移除 styleEl 与全部 inserted 样式（base 与转换后的
    // 样式表都在 inserted 中）；缺该方法时退化为逐项移除，避免重排后样式泄漏
    if (polisher && typeof polisher.destroy === 'function') {
      polisher.destroy()
      return
    }
    polisher?.inserted?.forEach((el) => el.remove())
    polisher?.base?.remove()
    polisher?.styleEl?.remove()
  }

  /** 销毁本次分页：移除渲染出的页面与注入的样式。 */
  dispose(): void {
    if (this.disposed) return
    this.disposed = true
    try {
      this.previewer?.chunker.destroy()
    } catch {
      /* pagesArea 可能已被移动或移除 */
    }
    this.disposeStyles()
  }
}
