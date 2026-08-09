/** 导出下载相关的纯函数。 */

/**
 * 从 Content-Disposition 响应头解析文件名：优先 RFC 5987 的 filename*（百分号编码），
 * 其次普通 filename="..."，都无法解析时回退到 fallback。
 */
export function extractFilename(header: string | null, fallback: string): string {
  if (header) {
    const star = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header)
    if (star) {
      try {
        return decodeURIComponent(star[1].trim())
      } catch {
        // 编码损坏时继续尝试普通 filename
      }
    }
    const plain = /filename\s*=\s*"([^"]+)"/.exec(header)
    if (plain) {
      return plain[1]
    }
  }
  return fallback
}
