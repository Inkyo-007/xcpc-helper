import { describe, expect, it } from 'vitest'
import { parseCredentialInput } from '@/features/activity/model/credentials'

const KEYS = ['_uid', '__client_id']

describe('parseCredentialInput', () => {
  it('解析 JSON 平铺形态', () => {
    const out = parseCredentialInput('{"_uid": "123", "__client_id": "abc"}', KEYS)
    expect(out).toEqual({ cookies: { _uid: '123', __client_id: 'abc' } })
  })

  it('解析 JSON 嵌套 cookies 形态', () => {
    const out = parseCredentialInput(
      '{"cookies": {"_uid": "123", "__client_id": "abc"}, "headers": {}}',
      KEYS,
    )
    expect(out).toEqual({ cookies: { _uid: '123', __client_id: 'abc' } })
  })

  it('解析 Cookie 头整串并提取所需字段', () => {
    const out = parseCredentialInput(
      '_uid=123; __client_id=abc; other_cookie=zzz',
      KEYS,
    )
    expect(out).toEqual({ cookies: { _uid: '123', __client_id: 'abc' } })
  })

  it('Cookie 值含等号时按首个等号切分', () => {
    const out = parseCredentialInput('_uid=123; __client_id=ab=c=', KEYS)
    expect(out?.cookies?.__client_id).toBe('ab=c=')
  })

  it('缺任一所需字段返回 null', () => {
    expect(parseCredentialInput('{"_uid": "123"}', KEYS)).toBeNull()
    expect(parseCredentialInput('_uid=123', KEYS)).toBeNull()
    expect(parseCredentialInput('_uid=123; __client_id=  ', KEYS)).toBeNull()
  })

  it('无法识别的输入返回 null', () => {
    expect(parseCredentialInput('', KEYS)).toBeNull()
    expect(parseCredentialInput('   ', KEYS)).toBeNull()
    expect(parseCredentialInput('随便一段文字', KEYS)).toBeNull()
    expect(parseCredentialInput('{not json', KEYS)).toBeNull()
    expect(parseCredentialInput('[1,2]', KEYS)).toBeNull()
  })

  it('所需字段为空时返回 null', () => {
    expect(parseCredentialInput('_uid=123', [])).toBeNull()
  })
})
