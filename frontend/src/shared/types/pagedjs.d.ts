/** pagedjs 0.4.x 的最小类型声明（官方未提供 TS 类型）。 */

declare module 'pagedjs' {
  export interface PagedPageInfo {
    element: HTMLElement
    id: string
  }

  export interface PagedFlow {
    pages: PagedPageInfo[]
    total: number
    performance: number
  }

  interface PagedPolisher {
    /** 注入到 document.head 的基础样式元素 */
    base: HTMLStyleElement | null
    /** 注入到 document.head 的转换后样式元素 */
    styleEl: HTMLStyleElement | null
    /** 所有通过 insert() 注入的样式元素（含 base 与转换后的样式表） */
    inserted: HTMLStyleElement[]
    /** 移除 styleEl 与全部 inserted 样式 */
    destroy(): void
  }

  interface PagedChunker {
    pagesArea?: HTMLElement
    destroy(): void
  }

  export class Previewer {
    constructor(options?: Record<string, unknown>)
    polisher: PagedPolisher
    chunker: PagedChunker
    preview(
      content: string,
      stylesheets: Array<string | Record<string, string>>,
      renderTo?: HTMLElement,
    ): Promise<PagedFlow>
  }
}
