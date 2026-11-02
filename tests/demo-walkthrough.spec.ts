import { describe, expect, it } from 'vitest'
import { analyzeBusinessHealth } from '../src/domain/businessHealth'
import { cityProfiles, syntheticPeers } from '../src/domain/benchmarkCases'
import { controlCase, mainCase } from '../src/domain/cases'
import { buildDemoStages } from '../src/domain/demoWalkthrough'
import { buildDiagnosis, type Assumptions } from '../src/domain/diagnosis'

const assumptions: Assumptions = {
  mode: 'reallocate',
  amount: 400,
  grossMargin: 0.45,
  marginalFactor: 0.8,
  merchantSubsidyDelta: 0,
}

describe('guided analysis evidence', () => {
  it('builds six evidence stages from real calculations', () => {
    const diagnosis = buildDiagnosis(mainCase, assumptions, 'ka')
    const health = analyzeBusinessHealth(mainCase, syntheticPeers, cityProfiles)
    const stages = buildDemoStages(mainCase, diagnosis, health)
    const text = stages.map((stage) => stage.metric).join(' | ')

    expect(stages.map((stage) => stage.id)).toEqual(['quality', 'results', 'funnel', 'commercial', 'customers', 'actions'])
    expect(text).toContain('归因定义一致')
    expect(text).toContain('60,000')
    expect(text).toContain('P1 10.0%')
    expect(text).toContain('ROI 10')
    expect(text).toContain('ROI 18')
    expect(text).toContain('4 家合格样本')
    expect(text).toContain('+2,560')
    expect(text).toContain('+1,152')
  })

  it('does not fabricate a result when attribution is inconsistent', () => {
    const diagnosis = buildDiagnosis(controlCase, assumptions, 'ka')
    const health = analyzeBusinessHealth(controlCase, syntheticPeers, cityProfiles)
    const stages = buildDemoStages(controlCase, diagnosis, health)

    expect(stages.at(-1)?.metric).toContain('先统一口径')
    expect(stages.at(-1)?.metric).not.toContain('预计')
  })
})
