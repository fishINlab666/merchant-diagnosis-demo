import { describe, expect, it } from 'vitest'
import { syntheticStoreCohort } from '../src/domain/benchmarkCases'
import { buildStoreSegments } from '../src/domain/storeSegments'

describe('KA store-level segmentation', () => {
  it('uses a deterministic 186-store synthetic cohort across four cities', () => {
    expect(syntheticStoreCohort).toHaveLength(186)
    expect(syntheticStoreCohort).toEqual(buildStoreSegments(syntheticStoreCohort).map(({ quadrant: _quadrant, ...store }) => store))
    expect(new Set(syntheticStoreCohort.map((store) => store.city))).toEqual(new Set(['杭州', '上海', '武汉', '成都']))
    expect(syntheticStoreCohort.every((store) => store.synthetic)).toBe(true)
  })

  it('classifies every store from its own growth and UE rather than a fixed display count', () => {
    const segments = buildStoreSegments(syntheticStoreCohort)
    const quadrants = new Set(segments.map((store) => store.quadrant))

    expect(segments).toHaveLength(186)
    expect(quadrants).toEqual(new Set(['scale', 'hold', 'adjust', 'fix']))
    for (const store of segments) {
      const expected = store.ue >= 0 ? store.growth >= 0.05 ? 'scale' : 'hold' : store.growth >= 0.05 ? 'adjust' : 'fix'
      expect(store.quadrant).toBe(expected)
    }
  })

  it('returns no store ranking for a real report without a store cohort', () => {
    expect(buildStoreSegments([])).toEqual([])
  })
})
