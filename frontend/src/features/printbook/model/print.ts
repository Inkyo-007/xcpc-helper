/**
 * 导出 PDF：把已分页的 DOM 临时移动到 body 直属的打印舞台，
 * 打印时隐藏应用其余部分，从而避开应用布局（grid/flex/overflow）对打印的干扰。
 * 打印前把 document.title 改为封面标题，决定"另存为 PDF"的默认文件名。
 */

export function printPages(pagesEl: HTMLElement, title: string): void {
  const parent = pagesEl.parentElement
  const next = pagesEl.nextSibling

  const stage = document.createElement('div')
  stage.className = 'pb-print-stage'
  stage.appendChild(pagesEl)
  document.body.appendChild(stage)

  const prevTitle = document.title
  document.title = title
  document.body.classList.add('pb-printing')

  let done = false
  const cleanup = (): void => {
    if (done) return
    done = true
    window.removeEventListener('afterprint', cleanup)
    if (parent) parent.insertBefore(pagesEl, next)
    stage.remove()
    document.title = prevTitle
    document.body.classList.remove('pb-printing')
  }

  window.addEventListener('afterprint', cleanup)
  window.print()
  // 兜底：部分环境（pywebview）不一定触发 afterprint；
  // Chrome 在打印对话框打开期间阻塞 JS，超时只会在对话框关闭后触发。
  window.setTimeout(cleanup, 60_000)
}
