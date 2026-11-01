import { describe, expect, it } from 'vitest'
import { demoStore } from '../src/domain/cases'
import { buildDataRequest, buildInitialObservations } from '../src/domain/intake'

describe('public information intake', () => {
  it('creates initial observations from public store information', () => {
    const observations = buildInitialObservations(demoStore)

    expect(observations.length).toBeGreaterThan(0)
    expect(observations.join(' ')).toContain('评分')
    expect(observations.join(' ')).toContain('一人食')
  })

  it('marks missing public evidence instead of creating a diagnosis from a shop name alone', () => {
    const observations = buildInitialObservations({
      ...demoStore,
      alias: '只有店名的门店',
      rating: Number.NaN,
      menuNote: '',
      priceBand: '',
    })

    expect(observations.join(' ')).toContain('公开信息不足')
    expect(observations.join(' ')).toContain('人工补充')
    expect(observations.join(' ')).not.toContain('ROI')
  })

  it('requests only one weekly report with the fields needed for budget decisions', () => {
    const request = buildDataRequest()

    expect(request.files).toHaveLength(1)
    expect(request.files[0]).toContain('周报')
    expect(request.fields).toEqual(expect.arrayContaining(['订单', '净GMV', '投放工具', '消耗', 'ROI', '商家补贴']))
    expect(request.exportSteps.length).toBeGreaterThan(0)
  })
})
