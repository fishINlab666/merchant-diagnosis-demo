import type { BusinessDimension, BusinessHealthResult } from './businessHealth'
import type { Calculation, DiagnosisResult, FollowUp, WeeklyReport } from './types'

export interface MerchantMetric {
  label: string
  value: string
  detail: string
}

export interface MerchantDimension extends BusinessDimension {
  decisionInsight: string
}

export interface MerchantDecisionCard {
  label: string
  value: string
  detail: string
}

export interface MerchantPerspective {
  role?: 'merchant' | 'ka' | 'cs'
  report: WeeklyReport
  pageTitle: string
  reportTitle: string
  decisionQuestion: string
  decisionSummary: string
  metrics: MerchantMetric[]
  dimensions: MerchantDimension[]
  module: {
    id: string
    title: string
    description: string
    cards: MerchantDecisionCard[]
  }
  calculation: Calculation | null
  followUps: FollowUp[]
  talkTracks: string[]
}

const methodInsights: Record<BusinessDimension['id'], string> = {
  storefront: '先检查评分、菜单、价格与门店承接',
  traffic: '按曝光 → P1 进店 → P2 下单定位漏斗',
  commercial: '先核对归因，再比较同口径工具效率',
  subsidy: '规模与毛利同看，拆补贴和让利',
  users: '看复购、会员与生命周期，不冒称 RFM',
  city: '只有同口径门店或城市样本时才做分层',
}

function dimensionOrder(diagnosis: DiagnosisResult): BusinessDimension['id'][] {
  const first = diagnosis.issues[0]?.code
  if (first === 'SUBSIDY' || first === 'PROFIT_RISK') return ['subsidy', 'commercial', 'traffic', 'storefront', 'users', 'city']
  if (first === 'ATTRIBUTION_MISMATCH' || first === 'ATTRIBUTION_IMMATURE') return ['commercial', 'traffic', 'subsidy', 'storefront', 'users', 'city']
  return ['commercial', 'traffic', 'subsidy', 'storefront', 'users', 'city']
}

function money(value: number): string {
  return `${Math.round(value).toLocaleString('zh-CN')} 元`
}

export function buildMerchantPerspective(
  report: WeeklyReport,
  health: BusinessHealthResult,
  diagnosis: DiagnosisResult,
): MerchantPerspective {
  const byId = new Map(health.dimensions.map((item) => [item.id, item]))
  const dimensions = dimensionOrder(diagnosis).map((id) => ({
    ...byId.get(id)!,
    decisionInsight: methodInsights[id],
  }))
  const firstIssue = diagnosis.issues[0]
  const firstFollowUp = diagnosis.followUps[0]
  const recommendation = diagnosis.recommendation
  const action = recommendation
    ? recommendation.mode === 'reallocate'
      ? `从${recommendation.sourceTool}向${recommendation.targetTool}挪移 ${recommendation.amount} 元`
      : `向${recommendation.targetTool}追加 ${recommendation.amount} 元`
    : firstIssue?.code === 'ATTRIBUTION_MISMATCH' || firstIssue?.code === 'ATTRIBUTION_IMMATURE'
      ? '先统一数据口径'
      : firstFollowUp?.action ?? '先补齐经营数据'
  const subsidyRate = report.netGmv === 0 ? 0 : report.merchantSubsidy / report.netGmv

  return {
    report,
    pageTitle: '我的经营诊断',
    reportTitle: '我的下周行动方案',
    decisionQuestion: '我的店钱漏在哪，下周先改什么？',
    decisionSummary: health.headline,
    metrics: [
      { label: '优先经营问题', value: `${diagnosis.issues.length} 项`, detail: '最多三项，数据异常优先于经营建议' },
      { label: '本周净 GMV', value: money(report.netGmv), detail: `${report.orders.toLocaleString('zh-CN')} 单 · ${report.store.category}` },
      { label: '商家补贴率', value: `${(subsidyRate * 100).toFixed(1)}%`, detail: `${money(report.merchantSubsidy)}，规模与利润一起复核` },
    ],
    dimensions,
    module: {
      id: 'merchant-action',
      title: '下周经营动作',
      description: '把诊断落到动作、负责人、复核指标和停止条件，不停留在报告呈现。',
      cards: [
        { label: '钱漏在哪', value: firstIssue?.title ?? '未发现明确异常', detail: firstIssue?.detail ?? '按当前数据保持周复核' },
        { label: '下周主动作', value: action, detail: firstFollowUp ? `负责人：${firstFollowUp.owner}` : '补齐数据后确定负责人' },
        { label: '复核与停止', value: firstFollowUp?.metric ?? '数据完整度', detail: firstFollowUp ? `${firstFollowUp.target}；停止：${firstFollowUp.stopCondition}` : '没有可靠数据时不生成经营动作' },
      ],
    },
    calculation: diagnosis.calculation,
    followUps: diagnosis.followUps.map((item) => ({
      ...item,
      owner: item.owner.replace('KA／运营', '门店运营'),
    })),
    talkTracks: diagnosis.talkTracks,
  }
}
