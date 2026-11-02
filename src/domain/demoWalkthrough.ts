import type { BusinessHealthResult } from './businessHealth'
import type { DiagnosisResult, WeeklyReport } from './types'

export interface DemoStage {
  id: 'quality' | 'results' | 'funnel' | 'commercial' | 'customers' | 'actions'
  title: string
  description: string
  metric: string
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

function signed(value: number): string {
  return `${value >= 0 ? '+' : ''}${Math.round(value).toLocaleString('zh-CN')} 元`
}

export function buildDemoStages(
  report: WeeklyReport,
  diagnosis: DiagnosisResult,
  health: BusinessHealthResult,
): DemoStage[] {
  const codes = new Set(diagnosis.issues.map((issue) => issue.code))
  const quality = codes.has('ATTRIBUTION_MISMATCH')
    ? '发现归因口径差异，先停止工具排名'
    : codes.has('ATTRIBUTION_IMMATURE') ? '归因窗口未成熟，只保留过程事实' : `${report.tools.length} 个工具 · 归因定义一致 · 窗口已成熟`
  const sorted = [...report.tools].sort((a, b) => a.roi - b.roi)
  const low = sorted[0]
  const high = sorted.at(-1)
  const subsidyRate = report.netGmv === 0 ? 0 : report.merchantSubsidy / report.netGmv
  const commercial = low && high
    ? `${low.toolName} ROI ${low.roi} vs ${high.toolName} ROI ${high.roi} · 补贴率 ${percent(subsidyRate)}`
    : '未提供可比较的投放工具'
  const customerParts = [
    report.repeatCustomerRate === undefined ? null : `复购 ${percent(report.repeatCustomerRate)}`,
    report.memberShare === undefined ? null : `会员 ${percent(report.memberShare)}`,
    `${health.sampleSize} 家合格样本`,
  ].filter(Boolean)
  const recommendation = diagnosis.recommendation
  const calculation = diagnosis.calculation
  const action = recommendation && calculation
    ? recommendation.mode === 'reallocate'
      ? `从${recommendation.sourceTool}向${recommendation.targetTool}挪移 ${recommendation.amount} 元`
      : `向${recommendation.targetTool}追加 ${recommendation.amount} 元`
    : codes.has('ATTRIBUTION_MISMATCH') || codes.has('ATTRIBUTION_IMMATURE') ? '先统一口径' : '先控制毛利风险'
  const actionMetric = recommendation && calculation
    ? `${action} · 预计 GMV ${signed(calculation.deltaGmv)} · 毛利 ${signed(calculation.deltaGrossProfit)}`
    : `${action}，不生成收益测算`
  return [
    { id: 'quality', title: '数据与口径校验', description: '先检查门店、工具、归因定义和窗口，再决定哪些分析可以开放。', metric: quality },
    { id: 'results', title: '经营结果拆解', description: '同时看订单、净 GMV 和补贴，不把规模增长直接等同于经营改善。', metric: `${report.orders.toLocaleString('zh-CN')} 单 · 净 GMV ${report.netGmv.toLocaleString('zh-CN')} 元 · 商家补贴 ${report.merchantSubsidy.toLocaleString('zh-CN')} 元` },
    { id: 'funnel', title: '流量承接分析', description: '按曝光 → 进店 → 下单定位漏斗问题，而不是先加投放。', metric: report.exposure !== undefined && report.visits !== undefined && report.exposure > 0 && report.visits > 0 ? `P1 ${percent(report.visits / report.exposure)} · P2 ${percent(report.orders / report.visits)}` : '曝光或进店未提供，不计算 P1／P2' },
    { id: 'commercial', title: '商业化与利润分析', description: '比较同口径工具效率，并复核补贴对毛利的影响。', metric: commercial },
    { id: 'customers', title: '用户与竞店复核', description: '结合复购、会员和同口径样本判断后续运营方向。', metric: customerParts.join(' · ') },
    { id: 'actions', title: '生成下周动作', description: '把问题落到预算动作、负责人、复核指标和停止条件。', metric: actionMetric },
  ]
}
