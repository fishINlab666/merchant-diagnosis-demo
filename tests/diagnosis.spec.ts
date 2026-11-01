import { describe, expect, it } from 'vitest'
import { controlCase, mainCase } from '../src/domain/cases'
import { buildDiagnosis, type Assumptions } from '../src/domain/diagnosis'

const assumptions: Assumptions = {
  mode: 'reallocate',
  amount: 400,
  grossMargin: 0.45,
  marginalFactor: 0.8,
  merchantSubsidyDelta: 0,
}

describe('budget diagnosis', () => {
  it('recommends moving budget from the ROI 10 tool to the ROI 18 tool and recalculates profit', () => {
    const result = buildDiagnosis(mainCase, assumptions)

    expect(result.recommendation).toMatchObject({
      sourceTool: '点金推广',
      targetTool: '搜索推广',
      amount: 400,
      mode: 'reallocate',
    })
    expect(result.calculation).toMatchObject({
      currentGmv: 60000,
      projectedGmv: 62560,
      deltaGmv: 2560,
      currentGrossProfit: 20600,
      projectedGrossProfit: 21752,
      deltaGrossProfit: 1152,
      spendDelta: 0,
    })
    expect(result.issues.length).toBeLessThanOrEqual(3)
  })

  it('does not rank tools or calculate a transfer when attribution windows differ', () => {
    const result = buildDiagnosis(controlCase, assumptions)

    expect(result.recommendation).toBeNull()
    expect(result.calculation).toBeNull()
    expect(result.issues.map((issue) => issue.code)).toContain('ATTRIBUTION_MISMATCH')
  })

  it('calculates additional budget separately from reallocation', () => {
    const result = buildDiagnosis(mainCase, { ...assumptions, mode: 'add' })

    expect(result.recommendation).toMatchObject({ sourceTool: null, targetTool: '搜索推广', mode: 'add' })
    expect(result.calculation).toMatchObject({ deltaGmv: 5760, deltaGrossProfit: 2192, spendDelta: 400 })
  })

  it('changes talk tracks for service providers and SaaS customer success', () => {
    const agency = buildDiagnosis(mainCase, assumptions, 'agency')
    const customerSuccess = buildDiagnosis(mainCase, assumptions, 'cs')

    expect(agency.talkTracks).toHaveLength(3)
    expect(customerSuccess.talkTracks).toHaveLength(3)
    expect(agency.talkTracks.join(' ')).toContain('新客户')
    expect(customerSuccess.talkTracks.join(' ')).toContain('续费')
  })

  it('changes issue priorities and follow-up actions while preserving calculations across roles', () => {
    const ka = buildDiagnosis(mainCase, assumptions, 'ka')
    const agency = buildDiagnosis(mainCase, assumptions, 'agency')
    const customerSuccess = buildDiagnosis(mainCase, assumptions, 'cs')

    expect(ka.issues.map((issue) => issue.code)).toEqual(['LOW_ROI', 'SUBSIDY'])
    expect(agency.issues.map((issue) => issue.code)).toEqual(['SUBSIDY', 'LOW_ROI'])
    expect(customerSuccess.issues.map((issue) => issue.code)).toEqual(['SUBSIDY', 'LOW_ROI'])
    expect(new Set([ka.followUps[0].action, agency.followUps[0].action, customerSuccess.followUps[0].action]).size).toBe(3)
    expect(new Set([ka.followUps[0].owner, agency.followUps[0].owner, customerSuccess.followUps[0].owner]).size).toBe(3)
    expect(ka.calculation).toEqual(agency.calculation)
    expect(agency.calculation).toEqual(customerSuccess.calculation)
  })

  it('keeps role-specific outputs in attribution and profit-risk branches', () => {
    const roles = ['ka', 'agency', 'cs'] as const
    const attribution = roles.map((role) => buildDiagnosis(controlCase, assumptions, role))
    const profitRisk = roles.map((role) => buildDiagnosis(mainCase, { ...assumptions, mode: 'add', grossMargin: 0.05 }, role))

    expect(new Set(attribution.map((result) => result.followUps[0].action)).size).toBe(3)
    expect(new Set(attribution.map((result) => result.talkTracks.join(' '))).size).toBe(3)
    expect(attribution.every((result) => result.recommendation === null && result.calculation === null)).toBe(true)
    expect(new Set(profitRisk.map((result) => result.followUps[0].action)).size).toBe(3)
    expect(new Set(profitRisk.map((result) => result.talkTracks.join(' '))).size).toBe(3)
    expect(profitRisk.every((result) => result.issues.some((issue) => issue.code === 'PROFIT_RISK'))).toBe(true)
  })

  it('creates a follow-up table with owners, metrics and a review date', () => {
    const result = buildDiagnosis(mainCase, assumptions)

    expect(result.followUps).toHaveLength(3)
    for (const item of result.followUps) {
      expect(item.owner).not.toBe('')
      expect(item.metric).not.toBe('')
      expect(item.reviewDate).toBe('2026-10-19')
      expect(item.stopCondition).not.toBe('')
    }
  })
})
