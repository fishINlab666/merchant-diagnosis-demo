import { describe, expect, it } from 'vitest'
import { parsePublicIntake, PUBLIC_INTAKE_SAMPLE } from '../src/domain/intake'

describe('public shop-page intake', () => {
  it('extracts confirmable shop facts, menu items and review text', () => {
    const result = parsePublicIntake(PUBLIC_INTAKE_SAMPLE)

    expect(result.facts).toMatchObject({
      name: '张记煲仔饭（城西店）',
      rating: 4.4,
      monthlySales: 2600,
      averagePrice: 29,
      minimumOrder: 20,
      deliveryFee: 4,
      deliveryMinutes: 42,
    })
    expect(result.facts.menuItems).toContain('一人食套餐（饭+例汤）¥35')
    expect(result.themes.find((theme) => theme.id === 'delivery')?.count).toBeGreaterThanOrEqual(2)
    expect(result.themes.find((theme) => theme.id === 'temperature')?.quotes[0]).toContain('饭都凉了')
  })

  it('uses only explicitly pasted competitors for comparison', () => {
    const result = parsePublicIntake(PUBLIC_INTAKE_SAMPLE)

    expect(result.competitors).toHaveLength(2)
    expect(result.peerSummary).toMatchObject({ ratingMedian: 4.65, deliveryMinutesMedian: 33 })
    expect(result.candidates.some((item) => item.evidence.includes('33 分钟'))).toBe(true)
  })

  it('creates at most three evidence-led candidates with a next action', () => {
    const result = parsePublicIntake(PUBLIC_INTAKE_SAMPLE)

    expect(result.candidates.length).toBeGreaterThan(0)
    expect(result.candidates.length).toBeLessThanOrEqual(3)
    for (const candidate of result.candidates) {
      expect(candidate.evidence).not.toBe('')
      expect(candidate.hypothesis).toContain('待验证')
      expect(candidate.action).not.toBe('')
    }
  })

  it('returns missing facts instead of inventing a diagnosis from a name', () => {
    const result = parsePublicIntake('只有店名的门店')

    expect(result.facts.name).toBe('只有店名的门店')
    expect(result.facts.rating).toBeNull()
    expect(result.themes).toEqual([])
    expect(result.competitors).toEqual([])
    expect(result.candidates).toEqual([])
  })
})
