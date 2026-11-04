import { describe, expect, it } from 'vitest'
import { analyzeBusinessHealth } from '../src/domain/businessHealth'
import { cityProfiles, syntheticPeers } from '../src/domain/benchmarkCases'
import { mainCase } from '../src/domain/cases'
import { buildCustomerHealth } from '../src/domain/customerHealth'

describe('SaaS customer health and intervention', () => {
  it('calculates a deterministic intervention score from explicit operating and usage signals', () => {
    const health = analyzeBusinessHealth(mainCase, syntheticPeers, cityProfiles)
    const result = buildCustomerHealth(mainCase, health, mainCase.productUsage)

    expect(result.score).toBe(45)
    expect(result.level).toBe('red')
    expect(result.renewalDays).toBe(45)
    expect(result.signals).toHaveLength(6)
    expect(result.signals.map((signal) => signal.label)).toEqual(expect.arrayContaining(['经营回报', '补贴依赖', '产品使用深度', '跟进回填', '最近活跃', '续费复核窗口']))
    expect(result.deductions.length).toBeGreaterThan(0)
  })

  it('never invents a renewal score when real product usage is missing', () => {
    const realReport = { ...mainCase, synthetic: false, productUsage: undefined }
    const health = analyzeBusinessHealth(realReport, [], [])
    const result = buildCustomerHealth(realReport, health, undefined)

    expect(result.score).toBeNull()
    expect(result.level).toBe('missing')
    expect(result.renewalDays).toBeNull()
    expect(result.signals.filter((signal) => signal.label !== '经营回报' && signal.label !== '补贴依赖').every((signal) => signal.value === '未提供')).toBe(true)
  })
})
