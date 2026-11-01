import { describe, expect, it } from 'vitest'
import { analyzeBusinessHealth } from '../src/domain/businessHealth'
import { cityProfiles, syntheticPeers } from '../src/domain/benchmarkCases'
import { controlCase, fineDiningCase, mainCase } from '../src/domain/cases'
import { buildDiagnosis, type Assumptions } from '../src/domain/diagnosis'
import { buildMerchantPerspective } from '../src/domain/merchantPerspective'

const assumptions: Assumptions = {
  mode: 'reallocate',
  amount: 400,
  grossMargin: 0.45,
  marginalFactor: 0.8,
  merchantSubsidyDelta: 0,
}

function perspective(report = mainCase) {
  const health = analyzeBusinessHealth(report, syntheticPeers, cityProfiles)
  const diagnosis = buildDiagnosis(report, assumptions, 'ka')
  return buildMerchantPerspective(report, health, diagnosis)
}

describe('merchant self-service diagnosis', () => {
  it('uses one merchant decision model instead of role presentation', () => {
    const result = perspective()

    expect(result.module.id).toBe('merchant-action')
    expect(result.decisionQuestion).toContain('我的店')
    expect(result.pageTitle).toBe('我的经营诊断')
    expect(result.reportTitle).toBe('我的下周行动方案')
    expect(result.module.cards).toHaveLength(3)
  })

  it('produces different problems and actions for different store inputs', () => {
    const fastFood = perspective()
    const fineDining = perspective(fineDiningCase)

    expect(fineDining.report.store.category).toBe('粤式正餐')
    expect(fineDining.module.cards[0].value).not.toBe(fastFood.module.cards[0].value)
    expect(fineDining.followUps.map((item) => item.action)).not.toEqual(fastFood.followUps.map((item) => item.action))
    expect(fineDining.calculation).not.toEqual(fastFood.calculation)
  })

  it('closes unsupported modules and budget calculations for inconsistent attribution', () => {
    const result = perspective(controlCase)

    expect(result.calculation).toBeNull()
    expect(result.dimensions.some((item) => item.status === 'missing' || item.status === 'watch' || item.status === 'risk')).toBe(true)
    expect(result.module.cards.map((card) => card.value).join(' ')).toContain('先统一数据口径')
    expect(result.followUps[0].action).toContain('统一')
  })
})
