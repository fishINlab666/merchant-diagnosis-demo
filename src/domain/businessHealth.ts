import type { WeeklyReport } from './types'

export type DimensionStatus = 'strong' | 'watch' | 'risk' | 'missing'
export type CityStrategy = 'scale' | 'fix-funnel' | 'fix-profit' | 'fix-basics'

export interface PeerSample {
  peerId: string
  alias: string
  synthetic: true
  platform: string
  city: string
  district: string
  category: string
  priceBand: string
  capturedAt: string
  rating: number
  p1: number
  p2: number
  netGmv: number
  subsidyRate: number
  repeatCustomerRate: number
  memberShare: number
}

export interface CityProfile {
  city: string
  synthetic: true
  platform: string
  category: string
  priceBand: string
  capturedAt: string
  ue: number
  growth: number
  netGmvMedian: number
  p2Median: number
  roiMedian: number
  subsidyRateMedian: number
}

export interface BusinessDimension {
  id: 'storefront' | 'traffic' | 'commercial' | 'subsidy' | 'users' | 'city'
  title: string
  status: DimensionStatus
  merchant: string
  comparison: string
  evidence: string
}

export interface CityAnalysis extends CityProfile {
  strategy: CityStrategy
}

export interface BusinessHealthResult {
  sampleSize: number
  peerMedian: Record<string, number> | null
  dimensions: BusinessDimension[]
  cities: CityAnalysis[]
  headline: string
  scope: string
}

export function median(values: number[]): number {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle]
}

export function eligiblePeers(report: WeeklyReport, peers: PeerSample[]): PeerSample[] {
  return peers.filter((peer) =>
    peer.platform === report.store.platform &&
    peer.city === report.store.city &&
    peer.district === report.store.district &&
    peer.category === report.store.category &&
    peer.priceBand === report.store.priceBand &&
    peer.capturedAt === report.weekStart)
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export function analyzeBusinessHealth(
  report: WeeklyReport,
  peers: PeerSample[],
  cities: CityProfile[],
): BusinessHealthResult {
  const eligible = eligiblePeers(report, peers)
  const peerMedian = eligible.length < 2 ? null : {
    rating: median(eligible.map((peer) => peer.rating)),
    p1: median(eligible.map((peer) => peer.p1)),
    p2: median(eligible.map((peer) => peer.p2)),
    netGmv: median(eligible.map((peer) => peer.netGmv)),
    subsidyRate: median(eligible.map((peer) => peer.subsidyRate)),
    repeatCustomerRate: median(eligible.map((peer) => peer.repeatCustomerRate)),
    memberShare: median(eligible.map((peer) => peer.memberShare)),
  }
  const totalSpend = report.tools.reduce((sum, tool) => sum + tool.spend, 0)
  const dominantSpend = Math.max(...report.tools.map((tool) => tool.spend))
  const dominantShare = totalSpend === 0 ? 0 : dominantSpend / totalSpend
  const subsidyRate = report.netGmv === 0 ? 0 : report.merchantSubsidy / report.netGmv
  const hasTraffic = report.exposure !== undefined && report.visits !== undefined && report.exposure > 0 && report.visits > 0
  const hasUsers = report.repeatCustomerRate !== undefined && report.memberShare !== undefined
  const dimensions: BusinessDimension[] = [
    {
      id: 'storefront', title: '门店基建', status: peerMedian && report.store.rating < peerMedian.rating ? 'watch' : 'strong',
      merchant: `公开评分 ${report.store.rating}`,
      comparison: peerMedian ? `样本中位数 ${peerMedian.rating}` : '合格样本不足',
      evidence: report.store.menuNote,
    },
    {
      id: 'traffic', title: '流量承接', status: hasTraffic ? 'watch' : 'missing',
      merchant: hasTraffic ? `P1 ${percent(report.visits! / report.exposure!)} · P2 ${percent(report.orders / report.visits!)}` : '未提供',
      comparison: peerMedian ? `样本 P1 ${percent(peerMedian.p1)} · P2 ${percent(peerMedian.p2)}` : '合格样本不足',
      evidence: hasTraffic ? '曝光 → 进店 → 下单按聚合后的分子分母重算' : '缺少曝光或进店字段，不计算转化率',
    },
    {
      id: 'commercial', title: '商业化结构', status: dominantShare > 0.5 ? 'watch' : 'strong',
      merchant: `最大工具消耗占比 ${percent(dominantShare)}`,
      comparison: '只比较同口径工具，不合成整体广告 ROI',
      evidence: report.tools.map((tool) => `${tool.toolName} ROI ${tool.roi}`).join(' · '),
    },
    {
      id: 'subsidy', title: '补贴与毛利', status: peerMedian && subsidyRate > peerMedian.subsidyRate ? 'risk' : 'strong',
      merchant: `商家补贴率 ${percent(subsidyRate)}`,
      comparison: peerMedian ? `样本中位数 ${percent(peerMedian.subsidyRate)}` : '合格样本不足',
      evidence: '补贴与投放分开核算，毛利沿用当前测算假设',
    },
    {
      id: 'users', title: '用户经营', status: hasUsers ? 'watch' : 'missing',
      merchant: hasUsers ? `复购 ${percent(report.repeatCustomerRate!)} · 会员 ${percent(report.memberShare!)}` : '未提供',
      comparison: peerMedian ? `复购 ${percent(peerMedian.repeatCustomerRate)} · 会员 ${percent(peerMedian.memberShare)}` : '合格样本不足',
      evidence: hasUsers ? '用于判断拉新、留存和会员运营，不把用户人数跨人群加总' : '缺少复购或会员字段，不输出用户结构结论',
    },
    {
      id: 'city', title: '城市与门店分层', status: peerMedian && report.netGmv < peerMedian.netGmv ? 'watch' : 'strong',
      merchant: `单店净 GMV ${report.netGmv.toLocaleString('zh-CN')} 元`,
      comparison: peerMedian ? `样本中位数 ${peerMedian.netGmv.toLocaleString('zh-CN')} 元` : '合格样本不足',
      evidence: '只表示同口径样本内位置，不代表城市或行业排名',
    },
  ]
  const cityResults = cities.map((city) => {
    const highUe = city.ue >= 0
    const highGrowth = city.growth >= 0.05
    const strategy: CityStrategy = highUe && highGrowth ? 'scale' : highUe ? 'fix-funnel' : highGrowth ? 'fix-profit' : 'fix-basics'
    return { ...city, strategy }
  })
  const headline = eligible.length < 2
    ? '合格竞店样本不足，只展示样本事实'
    : peerMedian && subsidyRate > peerMedian.subsidyRate && report.netGmv < peerMedian.netGmv
      ? '规模追赶期：先修补贴与转化，再扩大预算'
      : '同口径样本对比，先定位主要矛盾'
  return {
    sampleSize: eligible.length,
    peerMedian,
    dimensions,
    cities: cityResults,
    headline,
    scope: `${report.store.city} · ${report.store.district} · ${report.store.category} · ${report.store.priceBand} · ${report.weekStart}`,
  }
}
