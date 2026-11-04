import { describe, expect, it } from 'vitest'
import { mainCase } from '../src/domain/cases'
import { buildDemoSeries, buildTrendEvidence } from '../src/domain/demoSeries'

describe('synthetic weekly trend', () => {
  it('creates eight deterministic weeks that reconcile to the current report', () => {
    const series = buildDemoSeries(mainCase)

    expect(series).toHaveLength(8)
    expect(series).toEqual(buildDemoSeries(mainCase))
    expect(series.at(-1)).toEqual({
      weekStart: mainCase.weekStart,
      netGmv: 60000,
      spend: 2400,
      roi: 13.17,
    })
    expect(series[0].netGmv).toBeLessThan(series.at(-1)!.netGmv)
    expect(series[0].roi).toBeGreaterThan(series.at(-1)!.roi)
  })

  it('never fabricates history for an uploaded real report', () => {
    expect(buildDemoSeries({ ...mainCase, synthetic: false })).toEqual([])
  })

  it('turns eight-week spend growth and ROI decline into evidence', () => {
    expect(buildTrendEvidence(mainCase)).toMatchObject({
      spendGrowth: 0.3889,
      roiChange: -0.1071,
      firstRoi: 14.75,
      currentRoi: 13.17,
    })
    expect(buildTrendEvidence({ ...mainCase, synthetic: false })).toBeNull()
  })
})
