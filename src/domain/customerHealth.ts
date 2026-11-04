import type { BusinessHealthResult } from './businessHealth'
import type { ProductUsage, WeeklyReport } from './types'

export type HealthLevel = 'red' | 'yellow' | 'green' | 'missing'
export type SignalRisk = 'high' | 'medium' | 'low' | 'missing'

export interface CustomerHealthSignal {
  label: string
  value: string
  risk: SignalRisk
}

export interface CustomerHealthResult {
  score: number | null
  level: HealthLevel
  levelLabel: string
  renewalDays: number | null
  signals: CustomerHealthSignal[]
  deductions: string[]
}

function daysBetween(from: string, to: string): number {
  return Math.floor((Date.parse(to) - Date.parse(from)) / 86400000)
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export function buildCustomerHealth(
  report: WeeklyReport,
  health: BusinessHealthResult,
  usage?: ProductUsage,
): CustomerHealthResult {
  const sorted = [...report.tools].sort((a, b) => a.roi - b.roi)
  const low = sorted[0]
  const high = sorted.at(-1)
  const lowRoiSpread = Boolean(low && high && low.roi < high.roi * 0.75)
  const subsidyRate = report.netGmv > 0 ? report.merchantSubsidy / report.netGmv : 0
  const peerSubsidy = health.peerMedian?.subsidyRate
  const highSubsidy = peerSubsidy !== undefined && subsidyRate > peerSubsidy
  const dominantShare = report.tools.reduce((sum, tool) => sum + tool.spend, 0) > 0
    ? Math.max(...report.tools.map((tool) => tool.spend)) / report.tools.reduce((sum, tool) => sum + tool.spend, 0) : 0
  const inactiveDays = usage ? Math.max(0, daysBetween(usage.lastActiveDate, report.exportedAt)) : null
  const renewalDays = usage?.renewalReviewDate ? daysBetween(report.exportedAt, usage.renewalReviewDate) : null
  const signals: CustomerHealthSignal[] = [
    { label: '经营回报', value: low && high ? `最低 ROI ${low.roi} · 同口径最高 ${high.roi}` : '投放数据不足', risk: lowRoiSpread ? 'high' : low && high ? 'low' : 'missing' },
    { label: '补贴依赖', value: `${percent(subsidyRate)}${peerSubsidy !== undefined ? ` · 样本中位数 ${percent(peerSubsidy)}` : ' · 无同口径样本'}`, risk: peerSubsidy === undefined ? 'missing' : highSubsidy ? 'medium' : 'low' },
    { label: '产品使用深度', value: usage ? `${usage.activeOperators} 人活跃 · 周报导入 ${usage.weeklyImports} 次` : '未提供', risk: usage ? usage.weeklyImports < 1 ? 'high' : 'low' : 'missing' },
    { label: '跟进回填', value: usage ? percent(usage.followupCompletionRate) : '未提供', risk: usage ? usage.followupCompletionRate < 0.6 ? 'high' : usage.followupCompletionRate < 0.8 ? 'medium' : 'low' : 'missing' },
    { label: '最近活跃', value: usage ? `${usage.lastActiveDate} · ${inactiveDays} 天前` : '未提供', risk: usage ? inactiveDays! > 30 ? 'high' : inactiveDays! > 7 ? 'medium' : 'low' : 'missing' },
    { label: '续费复核窗口', value: usage?.renewalReviewDate && renewalDays !== null ? `${renewalDays} 天后 · ${usage.renewalReviewDate}` : '未提供', risk: renewalDays === null ? 'missing' : renewalDays <= 30 ? 'high' : renewalDays <= 60 ? 'medium' : 'low' },
  ]
  if (!usage) return { score: null, level: 'missing', levelLabel: '数据不足', renewalDays: null, signals, deductions: [] }
  const deductions: string[] = []
  let score = 100
  const deduct = (amount: number, label: string) => { score -= amount; deductions.push(`${label} -${amount}`) }
  if (lowRoiSpread) deduct(15, '工具回报差距')
  if (highSubsidy) deduct(15, '补贴高于同口径样本')
  if (dominantShare > 0.5) deduct(10, '预算过度集中')
  if (usage.weeklyImports < 1) deduct(15, '本周未导入周报')
  if (usage.followupCompletionRate < 0.6) deduct(20, '跟进回填不足')
  else if (usage.followupCompletionRate < 0.8) deduct(10, '跟进回填待改善')
  if (inactiveDays! > 30) deduct(20, '长期未活跃')
  else if (inactiveDays! > 7) deduct(10, '最近活跃下降')
  if (renewalDays !== null && renewalDays <= 30) deduct(10, '续费复核临近')
  else if (renewalDays !== null && renewalDays <= 60) deduct(5, '续费复核窗口')
  score = Math.max(0, Math.min(100, score))
  const level: HealthLevel = score < 50 ? 'red' : score < 75 ? 'yellow' : 'green'
  return { score, level, levelLabel: level === 'red' ? '红灯 · 优先干预' : level === 'yellow' ? '黄灯 · 本周复核' : '绿灯 · 保持跟踪', renewalDays, signals, deductions }
}
