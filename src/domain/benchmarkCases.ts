import type { CityProfile, PeerSample } from './businessHealth'

export { mainCase } from './cases'

const base = {
  synthetic: true as const,
  platform: '示例平台',
  city: '杭州',
  district: '城西科创商圈',
  category: '中式快餐',
  priceBand: '25—35 元',
  capturedAt: '2026-10-12',
}

export const syntheticPeers: PeerSample[] = [
  { ...base, peerId: 'P1', alias: '合成商户 B', rating: 4.6, p1: 0.12, p2: 0.11, netGmv: 65000, subsidyRate: 0.03, repeatCustomerRate: 0.33, memberShare: 0.30 },
  { ...base, peerId: 'P2', alias: '合成商户 C', rating: 4.5, p1: 0.13, p2: 0.12, netGmv: 70000, subsidyRate: 0.025, repeatCustomerRate: 0.35, memberShare: 0.32 },
  { ...base, peerId: 'P3', alias: '合成商户 D', rating: 4.7, p1: 0.11, p2: 0.10, netGmv: 62000, subsidyRate: 0.04, repeatCustomerRate: 0.31, memberShare: 0.28 },
  { ...base, peerId: 'P4', alias: '合成商户 E', rating: 4.6, p1: 0.12, p2: 0.11, netGmv: 68000, subsidyRate: 0.05, repeatCustomerRate: 0.34, memberShare: 0.31 },
  { ...base, peerId: 'PX', alias: '上海对照商户（应剔除）', city: '上海', district: '静安商圈', rating: 4.9, p1: 0.18, p2: 0.16, netGmv: 90000, subsidyRate: 0.01, repeatCustomerRate: 0.45, memberShare: 0.42 },
]

export const cityProfiles: CityProfile[] = [
  { city: '杭州', synthetic: true, platform: '示例平台', category: '中式快餐', priceBand: '25—35 元', capturedAt: '2026-10-12', ue: 0.08, growth: 0.03, netGmvMedian: 66500, p2Median: 0.11, roiMedian: 13, subsidyRateMedian: 0.035 },
  { city: '上海', synthetic: true, platform: '示例平台', category: '中式快餐', priceBand: '25—35 元', capturedAt: '2026-10-12', ue: 0.12, growth: 0.08, netGmvMedian: 82000, p2Median: 0.13, roiMedian: 16, subsidyRateMedian: 0.025 },
  { city: '武汉', synthetic: true, platform: '示例平台', category: '中式快餐', priceBand: '25—35 元', capturedAt: '2026-10-12', ue: -0.02, growth: 0.09, netGmvMedian: 71000, p2Median: 0.12, roiMedian: 11, subsidyRateMedian: 0.065 },
  { city: '成都', synthetic: true, platform: '示例平台', category: '中式快餐', priceBand: '25—35 元', capturedAt: '2026-10-12', ue: -0.03, growth: 0.01, netGmvMedian: 52000, p2Median: 0.08, roiMedian: 8, subsidyRateMedian: 0.07 },
]
