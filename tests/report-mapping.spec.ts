import { describe, expect, it } from 'vitest'
import { buildHeaderMapping } from '../src/lib/reportMapping'

const requiredHeaders = ['门店ID', '周开始', '订单', '净GMV', '商家补贴', '平台补贴', '投放工具', '消耗', '归因净GMV', '归因窗口', '归因定义', '导出时间']

describe('weekly report header mapping', () => {
  it('maps exact fields and opens all optional modules when optional fields exist', () => {
    const result = buildHeaderMapping([...requiredHeaders, '曝光', '进店', '复购率', '会员占比'])

    expect(result.canGenerate).toBe(true)
    expect(result.missingRequired).toEqual([])
    expect(result.duplicateStandards).toEqual([])
    expect(result.mappings.every((item) => item.match === 'exact')).toBe(true)
    expect(result.modules.find((item) => item.id === 'traffic')?.available).toBe(true)
    expect(result.modules.find((item) => item.id === 'users')?.available).toBe(true)
  })

  it('marks rule aliases as reviewable mappings instead of exact matches', () => {
    const result = buildHeaderMapping(['门店编号', '周期开始', '订单量', '净交易额', '商家补贴金额', '平台补贴金额', '工具名称', '广告消耗', '归因GMV', '归因窗口天数', '归因口径', '数据导出时间'])

    expect(result.canGenerate).toBe(true)
    expect(result.mappings.find((item) => item.source === '订单量')).toMatchObject({ standard: '订单', match: 'alias' })
    expect(result.mappings.find((item) => item.source === '归因GMV')).toMatchObject({ standard: '归因净GMV', match: 'alias' })
  })

  it('blocks generation and closes operations when required fields are missing', () => {
    const result = buildHeaderMapping(requiredHeaders.filter((header) => header !== '净GMV'))

    expect(result.canGenerate).toBe(false)
    expect(result.missingRequired).toEqual(['净GMV'])
    expect(result.modules.find((item) => item.id === 'operations')?.available).toBe(false)
  })

  it('blocks duplicate standard mappings instead of silently choosing a column', () => {
    const result = buildHeaderMapping([...requiredHeaders, '订单量'])

    expect(result.canGenerate).toBe(false)
    expect(result.duplicateStandards).toEqual(['订单'])
    expect(result.modules.find((item) => item.id === 'operations')?.reason).toContain('重复映射')
  })

  it('keeps unknown extra fields visible and closes only optional modules', () => {
    const result = buildHeaderMapping([...requiredHeaders, '活动名称'])

    expect(result.canGenerate).toBe(true)
    expect(result.mappings.find((item) => item.source === '活动名称')).toMatchObject({ standard: null, match: 'unmapped' })
    expect(result.modules.find((item) => item.id === 'traffic')?.available).toBe(false)
    expect(result.modules.find((item) => item.id === 'users')?.available).toBe(false)
  })
})
