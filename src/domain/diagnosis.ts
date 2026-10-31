import type {
  BudgetMode,
  Calculation,
  DiagnosisIssue,
  DiagnosisResult,
  Recommendation,
  Role,
  ToolMetric,
  WeeklyReport,
} from './types'

export interface Assumptions {
  mode: BudgetMode
  amount: number
  grossMargin: number
  marginalFactor: number
  merchantSubsidyDelta: number
}

function round(value: number): number {
  return Math.round(value * 100) / 100
}

function addDays(date: string, days: number): string {
  const value = new Date(`${date}T00:00:00Z`)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}

function comparable(tools: ToolMetric[]): boolean {
  return new Set(tools.map((tool) => `${tool.attributionDefinition}|${tool.attributionWindowDays}`)).size <= 1
}

function attributionMature(report: WeeklyReport): boolean {
  const lastDay = addDays(report.weekStart, 6)
  return report.tools.every((tool) => {
    const matureThrough = addDays(lastDay, tool.attributionWindowDays)
    return Date.parse(report.exportedAt) >= Date.parse(`${matureThrough}T00:00:00Z`)
  })
}

function makeCalculation(
  report: WeeklyReport,
  assumptions: Assumptions,
  recommendation: Recommendation,
  source: ToolMetric | null,
  target: ToolMetric,
): Calculation {
  const totalSpend = report.tools.reduce((sum, tool) => sum + tool.spend, 0)
  const isReallocate = recommendation.mode === 'reallocate'
  const spendDelta = isReallocate ? 0 : recommendation.amount
  const deltaGmv = isReallocate && source
    ? recommendation.amount * (target.roi - source.roi) * assumptions.marginalFactor
    : recommendation.amount * target.roi * assumptions.marginalFactor
  const currentGrossProfit = report.netGmv * assumptions.grossMargin - report.merchantSubsidy - totalSpend
  const projectedGmv = report.netGmv + deltaGmv
  const projectedGrossProfit = projectedGmv * assumptions.grossMargin
    - (report.merchantSubsidy + assumptions.merchantSubsidyDelta)
    - (totalSpend + spendDelta)
  return {
    currentGmv: report.netGmv,
    projectedGmv: round(projectedGmv),
    deltaGmv: round(deltaGmv),
    currentGrossProfit: round(currentGrossProfit),
    projectedGrossProfit: round(projectedGrossProfit),
    deltaGrossProfit: round(projectedGrossProfit - currentGrossProfit),
    spendDelta,
  }
}

function makeFollowUps(
  report: WeeklyReport,
  recommendation: Recommendation | null,
  issues: DiagnosisIssue[],
): DiagnosisResult['followUps'] {
  const reviewDate = addDays(report.weekStart, 7)
  const codes = new Set(issues.map((issue) => issue.code))
  if (codes.has('PROFIT_RISK')) {
    return [
      { action: '暂停追加预算', owner: 'KA／运营', metric: '毛利变化', target: '先保留当前预算作对照', reviewDate, stopCondition: '毛利测算未转正前不追加' },
      { action: '复核商家补贴与菜品让利', owner: '门店经营负责人', metric: '商家补贴占净 GMV 比例', target: '不高于本周水平', reviewDate, stopCondition: '补贴占比继续上升则暂停新增补贴' },
      { action: '调整假设后重新测算', owner: '商家外卖负责人', metric: '净 GMV、毛利', target: '毛利变化大于 0 且保留基线', reviewDate, stopCondition: '复核未通过则不进入追加' },
    ]
  }
  if (codes.has('BASIC_POOL')) {
    return [
      { action: '保留原工具基本盘', owner: '商家外卖负责人', metric: '原工具消耗与 ROI', target: '不做全量切换', reviewDate, stopCondition: '不得用单次 ROI 排名清空原工具' },
      { action: '只调整增量预算并设置对照', owner: 'KA／运营', metric: '增量消耗、净 GMV、毛利', target: '保留本周方案作对照', reviewDate, stopCondition: '实际 ROI 或毛利低于基线则停止增量' },
      { action: '复盘并决定继续、调整或回退', owner: 'KA／运营', metric: '净 GMV、毛利、执行完成度', target: '形成下周决策记录', reviewDate, stopCondition: '复核未通过则回退到本周方案' },
    ]
  }
  if (!recommendation) {
    return [
      { action: '统一各工具归因定义、窗口和成熟度', owner: '商家运营', metric: '归因口径', target: '全部工具一致且已成熟', reviewDate, stopCondition: '口径未对齐前不调整预算' },
      { action: '重新导出同口径周报', owner: '门店外卖负责人', metric: '周报完整度', target: '必需字段齐全', reviewDate, stopCondition: '字段不全或窗口未成熟时不出方案' },
      { action: '复核后再决定预算动作', owner: 'KA／运营', metric: '同口径 ROI', target: '完成人工复核并保留基线', reviewDate, stopCondition: '复核未通过则不进入追加' },
    ]
  }
  const action = recommendation.mode === 'reallocate'
    ? `从${recommendation.sourceTool}向${recommendation.targetTool}挪移 ${recommendation.amount} 元`
    : `向${recommendation.targetTool}追加 ${recommendation.amount} 元`
  return [
    { action, owner: '商家外卖负责人', metric: `${recommendation.targetTool} ROI、净 GMV`, target: '保留本周原预算方案作对照，记录实际值并对比测算', reviewDate, stopCondition: '目标工具 ROI 或毛利低于基线则回退' },
    { action: '复核商家补贴与菜品让利', owner: '门店经营负责人', metric: '商家补贴占净 GMV 比例', target: '不高于本周水平', reviewDate, stopCondition: '补贴占比继续上升则暂停新增补贴' },
    { action: '复盘并决定继续、调整或回退', owner: 'KA／运营', metric: '净 GMV、毛利、执行完成度', target: '形成下周决策记录', reviewDate, stopCondition: '实际结果未达到测算下限则停止追加并复盘' },
  ]
}

function makeTalkTracks(
  recommendation: Recommendation | null,
  calculation: Calculation | null,
  role: Role,
  issues: DiagnosisIssue[],
): string[] {
  const codes = new Set(issues.map((issue) => issue.code))
  if (codes.has('PROFIT_RISK')) {
    return [
      '按当前假设，追加后毛利不升反降，本周先不加预算。',
      '先优化预算结构和商家补贴，保留当前方案作对照。',
      '等毛利测算转正并有基线证据后，再讨论追加。',
    ]
  }
  if (codes.has('BASIC_POOL')) {
    return [
      '保留现有工具基本盘，不做全量切换。',
      '只调整增量预算或小步测试，并保留本周方案作对照。',
      '实际 ROI 和毛利优于基线后，再决定是否扩大调整。',
    ]
  }
  if (codes.has('ATTRIBUTION_IMMATURE')) {
    return [
      '当前归因窗口尚未成熟，先不根据 ROI 排名调预算。',
      '等导出时间覆盖最后一条记录的完整归因窗口再复盘。',
      '本周只跟进已知消耗和过程事实，不做收益预测。',
    ]
  }
  if (!recommendation || !calculation) {
    return [
      '目前工具归因窗口不同，先统一归因定义和窗口再比较。',
      '本周先补齐同口径周报，不急着调整预算。',
      '数据对齐后再评估追加或挪移，避免看错投入回报。',
    ]
  }
  const action = recommendation.mode === 'reallocate'
    ? `从${recommendation.sourceTool}挪 ${recommendation.amount} 元到${recommendation.targetTool}`
    : `向${recommendation.targetTool}追加 ${recommendation.amount} 元`
  if (role === 'agency') {
    return [
      '这份复盘可以直接变成你给客户的新增服务，不必每次都从零开始。',
      `建议${action}，用一页方案让客户看清调整和执行动作。`,
      '下周带复核结果再沟通，作为签下新客户或扩大服务范围的证据。',
    ]
  }
  if (role === 'cs') {
    return [
      '客户当前的健康风险主要在低效消耗和补贴，需要本周完成干预。',
      `建议${action}，把执行和复核记录留在客户健康档案里，降低续费风险。`,
      `下周重点看净 GMV 增加 ${calculation.deltaGmv} 元、毛利增加 ${calculation.deltaGrossProfit} 元的测算是否兑现。`,
    ]
  }
  return [
    `这周建议${action}，先把低效预算转到同口径高 ROI 工具。`,
    `按当前假设，净 GMV 预计增加 ${calculation.deltaGmv} 元，毛利预计增加 ${calculation.deltaGrossProfit} 元。`,
    '先执行一周并复核实际 ROI 和毛利，达到目标后再讨论是否继续加预算。',
  ]
}

export function buildDiagnosis(
  report: WeeklyReport,
  assumptions: Assumptions,
  role: Role = 'ka',
): DiagnosisResult {
  const issues: DiagnosisIssue[] = []
  const sameAttribution = comparable(report.tools)
  const mature = attributionMature(report)
  if (!sameAttribution) {
    issues.push({
      code: 'ATTRIBUTION_MISMATCH',
      title: '工具归因口径不同',
      value: report.tools.length,
      detail: '先统一归因定义和窗口，再决定是否挪预算',
    })
  }
  if (!mature) {
    const windowDays = Math.max(...report.tools.map((tool) => tool.attributionWindowDays))
    issues.push({
      code: 'ATTRIBUTION_IMMATURE',
      title: '归因窗口尚未成熟',
      value: windowDays,
      detail: '导出时间需覆盖最后一条记录的完整归因窗口',
    })
  }
  const sorted = [...report.tools].sort((a, b) => a.roi - b.roi)
  const source = sorted[0] ?? null
  const target = sorted.at(-1) ?? null
  if (source && target && sameAttribution && mature) {
    issues.push({
      code: 'LOW_ROI',
      title: `${source.toolName} ROI 偏低`,
      value: source.spend,
      detail: `当前 ROI ${source.roi}，同口径 ${target.toolName} ROI ${target.roi}`,
    })
  }
  if (report.merchantSubsidy > 0) {
    issues.push({
      code: 'SUBSIDY',
      title: '商家补贴需要复核',
      value: report.merchantSubsidy,
      detail: `占门店净 GMV ${(report.merchantSubsidy / report.netGmv * 100).toFixed(1)}%`,
    })
  }

  let recommendation: Recommendation | null = null
  let calculation: Calculation | null = null
  if (target && sameAttribution && mature && assumptions.amount > 0) {
    if (assumptions.mode === 'add') {
      const candidate: Recommendation = { mode: 'add', sourceTool: null, targetTool: target.toolName, amount: assumptions.amount }
      const scenario = makeCalculation(report, assumptions, candidate, null, target)
      if (scenario.deltaGrossProfit < 0) {
        issues.push({
          code: 'PROFIT_RISK',
          title: '追加后毛利不升反降',
          value: Math.abs(scenario.deltaGrossProfit),
          detail: `按当前假设毛利变化 ${scenario.deltaGrossProfit} 元，先优化预算结构`,
        })
      } else {
        recommendation = candidate
        calculation = scenario
      }
    } else if (source && source.toolName !== target.toolName) {
      if (assumptions.amount >= source.spend) {
        issues.push({
          code: 'BASIC_POOL',
          title: '不能用全量切换替代基本盘',
          value: source.spend,
          detail: '保留基本盘，改为小步测试或只调整增量预算',
        })
      } else {
        recommendation = { mode: 'reallocate', sourceTool: source.toolName, targetTool: target.toolName, amount: assumptions.amount }
        calculation = makeCalculation(report, assumptions, recommendation, source, target)
      }
    }
  }

  return {
    issues: issues.slice(0, 3),
    recommendation,
    calculation,
    talkTracks: makeTalkTracks(recommendation, calculation, role, issues),
    followUps: makeFollowUps(report, recommendation, issues),
  }
}
