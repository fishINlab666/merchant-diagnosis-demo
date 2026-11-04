import { describe, expect, it } from 'vitest'
import { analyzeBusinessHealth } from '../src/domain/businessHealth'
import { cityProfiles, syntheticPeers } from '../src/domain/benchmarkCases'
import { mainCase } from '../src/domain/cases'
import { buildCitySegments, CITY_SEGMENT_ACTIONS } from '../src/domain/citySegments'

describe('KA city resource segmentation', () => {
  it('maps growth and UE into four actionable quadrants', () => {
    const health = analyzeBusinessHealth(mainCase, syntheticPeers, cityProfiles)
    const segments = buildCitySegments(health.cities)

    expect(segments.map((item) => item.quadrant)).toEqual(['hold', 'scale', 'adjust', 'fix'])
    expect(segments.map((item) => item.city)).toEqual(['杭州', '上海', '武汉', '成都'])
    expect(CITY_SEGMENT_ACTIONS.scale).toContain('加推广')
    expect(CITY_SEGMENT_ACTIONS.fix).toContain('停推广')
  })

  it('returns no ranking when real data has no comparable cities', () => {
    expect(buildCitySegments([])).toEqual([])
  })
})
