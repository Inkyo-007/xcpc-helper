import { describe, expect, it } from 'vitest'

import { extractFilename } from '@/features/transfer/model/download'

describe('extractFilename', () => {
  it('优先解析 RFC 5987 filename*', () => {
    expect(
      extractFilename("attachment; filename*=UTF-8''xcpc-templates-20260810.zip", 'f.zip'),
    ).toBe('xcpc-templates-20260810.zip')
  })

  it('filename* 含中文时按百分号解码', () => {
    const header = `attachment; filename*=UTF-8''${encodeURIComponent('示例打印册.zip')}`
    expect(extractFilename(header, 'f.zip')).toBe('示例打印册.zip')
  })

  it('无 filename* 时退而解普通 filename', () => {
    expect(extractFilename('attachment; filename="a.zip"', 'f.zip')).toBe('a.zip')
  })

  it('头部缺失或无法解析时回退默认名', () => {
    expect(extractFilename(null, 'f.zip')).toBe('f.zip')
    expect(extractFilename('attachment', 'f.zip')).toBe('f.zip')
    expect(extractFilename("attachment; filename*=UTF-8''%zz", 'f.zip')).toBe('f.zip')
  })
})
