import { describe, expect, it } from 'vitest'
import { mainCase } from '../src/domain/cases'
import { buildDemoSeries } from '../src/domain/demoSeries'

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
})
