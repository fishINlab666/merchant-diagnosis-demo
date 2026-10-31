import { describe, expect, it } from 'vitest'
import { mainCase, cityProfiles, syntheticPeers } from '../src/domain/benchmarkCases'
import { analyzeBusinessHealth, eligiblePeers, median } from '../src/domain/businessHealth'

describe('business health', () => {
  it('filters peers by scope and computes medians', () => {
    const eligible = eligiblePeers(mainCase, syntheticPeers)
    expect(eligible.length).toBeGreaterThanOrEqual(2)
    expect(median([10, 18, 12])).toBe(12)
  })

  it('degrades missing funnel and user fields instead of fabricating metrics', () => {
    const result = analyzeBusinessHealth({
      ...mainCase,
      exposure: undefined,
      visits: undefined,
      repeatCustomerRate: undefined,
      memberShare: undefined,
    }, syntheticPeers, cityProfiles)
    expect(result.dimensions.find((item) => item.id === 'traffic')?.status).toBe('missing')
    expect(result.dimensions.find((item) => item.id === 'users')?.status).toBe('missing')
  })

  it('does not output a median below two eligible peers', () => {
    const result = analyzeBusinessHealth(mainCase, syntheticPeers.slice(0, 1), cityProfiles)
    expect(result.peerMedian).toBeNull()
    expect(result.sampleSize).toBe(1)
  })

  it('covers six dimensions and all four UE growth strategies', () => {
    const result = analyzeBusinessHealth(mainCase, syntheticPeers, cityProfiles)
    expect(result.dimensions.map((item) => item.id)).toEqual(['storefront', 'traffic', 'commercial', 'subsidy', 'users', 'city'])
    expect(new Set(result.cities.map((item) => item.strategy)).size).toBe(4)
  })
})
