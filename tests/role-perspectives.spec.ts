import { describe, expect, it } from 'vitest'
import { analyzeBusinessHealth } from '../src/domain/businessHealth'
import { cityProfiles, syntheticPeers } from '../src/domain/benchmarkCases'
import { mainCase } from '../src/domain/cases'
import { buildDiagnosis, type Assumptions } from '../src/domain/diagnosis'
import { buildRolePerspective, type DecisionRole } from '../src/domain/rolePerspectives'

const assumptions: Assumptions = {
  mode: 'reallocate',
  amount: 400,
  grossMargin: 0.45,
  marginalFactor: 0.8,
  merchantSubsidyDelta: 0,
}

function perspective(role: DecisionRole) {
  const health = analyzeBusinessHealth(mainCase, syntheticPeers, cityProfiles)
  return buildRolePerspective(role, mainCase, health, buildDiagnosis(mainCase, assumptions, role))
}

describe('three role decision perspectives', () => {
  it('changes complete decision modules and six-dimension order instead of only changing copy', () => {
    const merchant = perspective('merchant')
    const ka = perspective('ka')
    const cs = perspective('cs')

    expect([merchant.module.id, ka.module.id, cs.module.id]).toEqual(['merchant-action', 'ka-jbp', 'cs-health'])
    expect(merchant.dimensions.map((item) => item.id)).toEqual(['commercial', 'traffic', 'subsidy', 'storefront', 'users', 'city'])
    expect(ka.dimensions.map((item) => item.id)).toEqual(['commercial', 'subsidy', 'traffic', 'city', 'storefront', 'users'])
    expect(cs.dimensions.map((item) => item.id)).toEqual(['users', 'subsidy', 'traffic', 'commercial', 'storefront', 'city'])
    expect(new Set([merchant.module.title, ka.module.title, cs.module.title]).size).toBe(3)
    expect(ka.module.cards.map((card) => card.label).join(' ')).toContain('JBP')
    expect(cs.module.cards.map((card) => card.label).join(' ')).toContain('使用')
  })

  it('keeps facts and calculations identical while changing role follow-ups', () => {
    const merchant = perspective('merchant')
    const ka = perspective('ka')
    const cs = perspective('cs')

    expect(ka.calculation).toEqual(merchant.calculation)
    expect(cs.calculation).toEqual(merchant.calculation)
    expect(ka.dimensions.map((item) => item.merchant).sort()).toEqual(merchant.dimensions.map((item) => item.merchant).sort())
    expect(cs.dimensions.map((item) => item.merchant).sort()).toEqual(merchant.dimensions.map((item) => item.merchant).sort())
    expect(new Set([merchant.followUps[0].action, ka.followUps[0].action, cs.followUps[0].action]).size).toBe(3)
  })

  it('uses role-specific report purposes and decision metrics', () => {
    const merchant = perspective('merchant')
    const ka = perspective('ka')
    const cs = perspective('cs')

    expect(merchant.reportTitle).toContain('下周')
    expect(ka.reportTitle).toContain('JBP')
    expect(cs.reportTitle).toContain('续费')
    expect(ka.metrics.map((metric) => metric.label)).toContain('城市样本')
    expect(cs.metrics.map((metric) => metric.label)).toContain('产品使用')
    expect(cs.metrics.find((metric) => metric.label === '产品使用')?.value).toContain('3 人')
    expect(cs.metrics.find((metric) => metric.label === '续费复核')?.value).toBe('2026-12-10')
    expect(cs.module.cards.find((card) => card.label === '使用深度')?.value).toContain('35.0%')
  })
})
