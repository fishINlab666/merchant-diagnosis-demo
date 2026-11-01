import { describe, expect, it } from 'vitest'
import { demoStore } from '../src/domain/cases'
import { searchPublicMerchant } from '../src/domain/publicSearch'

const profile = { ...demoStore, alias: '示例餐饮店' }

describe('public merchant search', () => {
  it('returns reviewable public observations with sources instead of verified facts', async () => {
    const result = await searchPublicMerchant(profile, async () => new Response('# 示例餐饮店\n评分：4.6\n人均 ¥35\n这是一段足够长的公开网页摘要，用于测试门店公开信息读取和人工复核流程。'))

    expect(result.status).toBe('review')
    expect(result.sources).toHaveLength(1)
    expect(result.sources[0].url).toContain('google.com/search')
    expect(result.sources[0].capturedAt).toMatch(/^\d{4}-\d{2}-\d{2}T/)
    expect(result.observations.join(' ')).toContain('待确认')
    expect(result.observations.join(' ')).toContain('4.6')
    expect(result.observations.join(' ')).toContain('35')
    expect(result.observations.join(' ')).toContain('周报')
  })

  it('falls back to manual intake when no usable public text is found', async () => {
    const result = await searchPublicMerchant(profile, async () => new Response('No results'))

    expect(result.status).toBe('manual')
    expect(result.sources).toEqual([])
    expect(result.observations.join(' ')).toContain('人工补充')
  })

  it('falls back to manual intake on request failure without inventing sources', async () => {
    const result = await searchPublicMerchant(profile, async () => { throw new Error('timeout') })

    expect(result.status).toBe('manual')
    expect(result.sources).toEqual([])
    expect(result.error).toContain('timeout')
    expect(result.observations.join(' ')).toContain('人工补充')
  })

  it('rejects access-denied pages as evidence', async () => {
    const result = await searchPublicMerchant(profile, async () => new Response('Access Denied. Your request has been blocked by the website security policy.'))

    expect(result.status).toBe('manual')
    expect(result.sources).toEqual([])
  })
})
