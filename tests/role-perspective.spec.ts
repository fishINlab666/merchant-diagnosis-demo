import { describe, expect, it } from 'vitest'
import { controlCase, mainCase, mainProductUsage } from '../src/domain/cases'
import { analyzeBusinessHealth } from '../src/domain/businessHealth'
import { cityProfiles, syntheticPeers } from '../src/domain/benchmarkCases'
import { buildDiagnosis, type Assumptions } from '../src/domain/diagnosis'
import { buildRolePerspective } from '../src/domain/rolePerspective'

const assumptions: Assumptions = {
  mode: 'reallocate',
  amount: 400,
  grossMargin: 0.45,
  marginalFactor: 0.8,
  merchantSubsidyDelta: 0,
}

function inputs(report = mainCase) {
  return {
    health: analyzeBusinessHealth(report, syntheticPeers, cityProfiles),
    diagnosis: buildDiagnosis(report, assumptions, 'ka'),
  }
}

describe('role decision perspectives', () => {
  it('builds three different decision modules instead of three labels', () => {
    const { health, diagnosis } = inputs()
    const ka = buildRolePerspective('ka', mainCase, health, diagnosis, null)
    const agency = buildRolePerspective('agency', mainCase, health, diagnosis, null)
    const cs = buildRolePerspective('cs', mainCase, health, diagnosis, mainProductUsage)

    expect(ka.module.id).toBe('jbp-budget')
    expect(agency.module.id).toBe('acquisition-delivery')
    expect(cs.module.id).toBe('health-renewal')
    expect(new Set([ka.pageTitle, agency.pageTitle, cs.pageTitle]).size).toBe(3)
    expect(new Set([ka.decisionQuestion, agency.decisionQuestion, cs.decisionQuestion]).size).toBe(3)
  })

  it('changes six-dimension priorities and role lenses without changing shared facts', () => {
    const { health, diagnosis } = inputs()
    const ka = buildRolePerspective('ka', mainCase, health, diagnosis, null)
    const agency = buildRolePerspective('agency', mainCase, health, diagnosis, null)
    const cs = buildRolePerspective('cs', mainCase, health, diagnosis, mainProductUsage)
    const facts = (perspective: typeof ka) => Object.fromEntries(perspective.dimensions.map((item) => [
      item.id,
      [item.title, item.merchant, item.comparison, item.evidence],
    ]))

    expect(ka.dimensions.map((item) => item.id)).toEqual(['commercial', 'subsidy', 'traffic', 'city', 'storefront', 'users'])
    expect(agency.dimensions.map((item) => item.id)).toEqual(['storefront', 'traffic', 'subsidy', 'users', 'commercial', 'city'])
    expect(cs.dimensions.map((item) => item.id)).toEqual(['users', 'subsidy', 'traffic', 'commercial', 'storefront', 'city'])
    expect(facts(agency)).toEqual(facts(ka))
    expect(facts(cs)).toEqual(facts(ka))
    expect(new Set(ka.dimensions.map((item, index) => item.roleInsight + agency.dimensions[index].roleInsight + cs.dimensions[index].roleInsight)).size).toBeGreaterThan(1)
  })

  it('returns role-specific decision metrics with real values or explicit data states', () => {
    const { health, diagnosis } = inputs()
    const ka = buildRolePerspective('ka', mainCase, health, diagnosis, null)
    const agency = buildRolePerspective('agency', mainCase, health, diagnosis, null)
    const cs = buildRolePerspective('cs', mainCase, health, diagnosis, mainProductUsage)

    expect(ka.metrics.map((item) => item.label)).toEqual(['优先预算问题', '预计净 GMV 变化', '预计毛利变化'])
    expect(agency.metrics.map((item) => item.label)).toEqual(['首聊服务切口', '本周交付动作', '客户复核日期'])
    expect(cs.metrics.map((item) => item.label)).toEqual(['经营风险信号', '产品使用深度', '干预优先级'])
    expect(ka.metrics[1].value).toContain('2,560')
    expect(agency.metrics[1].value).toBe('3 项')
    expect(cs.metrics[1].value).not.toBe('未提供')
  })

  it('degrades SaaS renewal analysis when product usage is unavailable', () => {
    const main = inputs()
    const available = buildRolePerspective('cs', mainCase, main.health, main.diagnosis, mainProductUsage)
    const control = inputs(controlCase)
    const missing = buildRolePerspective('cs', controlCase, control.health, control.diagnosis, null)

    expect(available.usage.status).toBe('available')
    expect(available.usage.riskLevel).not.toBeNull()
    expect(missing.usage.status).toBe('missing')
    expect(missing.usage.riskLevel).toBeNull()
    expect(missing.metrics[1].value).toBe('未提供')
    expect(missing.module.cards.map((card) => card.detail).join(' ')).toContain('补充产品使用数据')
  })
})
