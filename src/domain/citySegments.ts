import type { CityAnalysis } from './businessHealth'

export type CityQuadrant = 'scale' | 'hold' | 'adjust' | 'fix'

export interface CitySegment extends CityAnalysis {
  quadrant: CityQuadrant
}

export const CITY_SEGMENT_LABELS: Record<CityQuadrant, string> = {
  scale: '加码',
  hold: '稳住',
  adjust: '调结构',
  fix: '收缩整改',
}

export const CITY_SEGMENT_ACTIONS: Record<CityQuadrant, string> = {
  scale: '加推广，争取平台资源位和费率支持',
  hold: '保持基本盘，做新品和套餐拉增长',
  adjust: '先收补贴、调工具，再谈扩大投入',
  fix: '停推广，先修评分、出餐和菜单',
}

export function buildCitySegments(cities: CityAnalysis[]): CitySegment[] {
  return cities.map((city) => ({
    ...city,
    quadrant: city.ue >= 0
      ? city.growth >= 0.05 ? 'scale' : 'hold'
      : city.growth >= 0.05 ? 'adjust' : 'fix',
  }))
}
