import type { CityQuadrant } from './citySegments'

export interface StoreSegmentSample {
  storeId: string
  alias: string
  city: string
  synthetic: true
  growth: number
  ue: number
  netGmv: number
  capturedAt: string
}

export interface StoreSegment extends StoreSegmentSample {
  quadrant: CityQuadrant
}

export function buildStoreSegments(stores: StoreSegmentSample[]): StoreSegment[] {
  return stores.map((store) => ({
    ...store,
    quadrant: store.ue >= 0
      ? store.growth >= 0.05 ? 'scale' : 'hold'
      : store.growth >= 0.05 ? 'adjust' : 'fix',
  }))
}
