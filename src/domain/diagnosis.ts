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
  period?: 'week' | 'month'
  subsidyOrderLossRate?: number
}

function round(value: number): number {
  const rounded = Math.round(value * 100) / 100
  return rounded === 0 ? 0 : rounded
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
  const periodMultiplier = assumptions.period === 'month' ? 4.3 : 1
  const totalSpend = report.tools.reduce((sum, tool) => sum + tool.spend, 0) * periodMultiplier
  const isReallocate = recommendation.mode === 'reallocate'
  const spendDelta = (isReallocate ? 0 : recommendation.amount) * periodMultiplier
  const weeklyBudgetGmvDelta = isReallocate && source
    ? recommendation.amount * (target.roi - source.roi) * assumptions.marginalFactor
    : recommendation.amount * target.roi * assumptions.marginalFactor
  const budgetGmvDelta = weeklyBudgetGmvDelta * periodMultiplier
  const subsidyDelta = assumptions.merchantSubsidyDelta * periodMultiplier
  const subsidyOrderLossRate = Math.min(1, Math.max(0, assumptions.subsidyOrderLossRate ?? 0.4))
  const orderLossGmv = Math.max(0, -subsidyDelta) * subsidyOrderLossRate
  const deltaGmv = budgetGmvDelta - orderLossGmv
  const currentGmv = report.netGmv * periodMultiplier
  const currentGrossProfit = currentGmv * assumptions.grossMargin
    - report.merchantSubsidy * periodMultiplier - totalSpend
  const projectedGmv = currentGmv + deltaGmv
  const projectedGrossProfit = projectedGmv * assumptions.grossMargin
    - (report.merchantSubsidy * periodMultiplier + subsidyDelta)
    - (totalSpend + spendDelta)
  return {
    currentGmv: round(currentGmv),
    projectedGmv: round(projectedGmv),
    deltaGmv: round(deltaGmv),
    currentGrossProfit: round(currentGrossProfit),
    projectedGrossProfit: round(projectedGrossProfit),
    deltaGrossProfit: round(projectedGrossProfit - currentGrossProfit),
    spendDelta: round(spendDelta),
    budgetContribution: round(budgetGmvDelta * assumptions.grossMargin - spendDelta),
    subsidyContribution: round(-subsidyDelta),
    orderLossContribution: round(-orderLossGmv * assumptions.grossMargin),
  }
}

function makeFollowUps(
  report: WeeklyReport,
  recommendation: Recommendation | null,
  issues: DiagnosisIssue[],
  role: Role,
): DiagnosisResult['followUps'] {
  const reviewDate = addDays(report.weekStart, 7)
  const codes = new Set(issues.map((issue) => issue.code))
  if (role === 'agency') {
    const blocked = codes.has('ATTRIBUTION_MISMATCH') || codes.has('ATTRIBUTION_IMMATURE')
    return [
      {
        action: blocked ? '与客户确认周报口径并补齐授权数据' : '用公开初诊与客户确认首要经营问题',
        owner: blocked ? '服务商交付负责人' : '服务商 BD',
        metric: blocked ? '周报完整度／归因口径' : '客户确认的主要问题',
        target: blocked ? '客户确认一份可用周报' : `确认 1 个优先问题：${issues[0]?.title ?? '经营承接'}`,
        stopCondition: '客户未认可或口径未确认前，不承诺调整收益',
        reviewDate,
      },
      {
        action: '交付本周运营动作包并记录执行',
        owner: '代运营负责人',
        metric: '交付动作完成率',
        target: recommendation ? '完成预算动作、补贴复核与执行留痕' : '完成数据补齐与门店承接复核',
        stopCondition: '未实际执行不得包装成客户案例',
        reviewDate,
      },
      {
        action: '带前后数据复核并推进续约或扩服',
        owner: '服务商客户负责人',
        metric: '净 GMV、毛利、复核完成度',
        target: `${reviewDate} 前形成同口径复核记录`,
        stopCondition: '未留下执行与前后数据时，不作为签客成果',
        reviewDate,
      },
    ]
  }
  if (role === 'cs') {
    return [
      {
        action: '完成经营风险干预并记录客户确认',
        owner: '客户成功经理',
        metric: '经营风险信号、客户确认',
        target: `优先处理：${issues[0]?.title ?? '主要经营风险'}`,
        stopCondition: '客户未确认或数据异常时先补证据',
        reviewDate,
      },
      {
        action: '检查周报导入与跟进回填，补齐使用数据',
        owner: '客户成功经理／客户管理员',
        metric: '周报导入次数、跟进回填率',
        target: '建立可用使用基线并完成本周回填',
        stopCondition: '使用数据缺失时不生成续费风险等级',
        reviewDate,
      },
      {
        action: '复核干预结果并更新续费风险',
        owner: '客户成功主管',
        metric: '风险信号解除、净 GMV、毛利',
        target: `${reviewDate} 完成干预复核`,
        stopCondition: '风险未解除则升级客户成功与运营联合介入',
        reviewDate,
      },
    ]
  }
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
  const action = recommendation
    ? recommendation.mode === 'reallocate'
      ? `从${recommendation.sourceTool}挪 ${recommendation.amount} 元到${recommendation.targetTool}`
      : `向${recommendation.targetTool}追加 ${recommendation.amount} 元`
    : ''
  if (role === 'agency') {
    if (codes.has('PROFIT_RISK')) return [
      '这份复盘应先作为毛利修复服务，而不是追加预算方案。',
      '与客户确认补贴和低效消耗，交付一周毛利修复动作。',
      '留下执行与前后数据，再作为续约或新客沟通证据。',
    ]
    if (codes.has('BASIC_POOL')) return [
      '把全量切换风险转成客户交付规则，保留原工具基本盘。',
      '只交付增量测试与补贴复核，不把单次 ROI 当成签客承诺。',
      '下周用执行记录和同口径结果复核服务价值。',
    ]
    if (!recommendation || !calculation) return [
      '先把周报口径对齐作为本周的数据交付，不急着向客户承诺收益。',
      '帮助客户补齐归因定义、窗口和导出时间，再确认运营动作。',
      '数据对齐后交付预算方案，并保留新客户复核证据。',
    ]
    return [
      '这份复盘可以直接变成你给客户的新增服务，不必每次都从零开始。',
      `建议${action}，用一页方案让客户看清调整和执行动作。`,
      '下周带复核结果再沟通，作为签下新客户或扩大服务范围的证据。',
    ]
  }
  if (role === 'cs') {
    if (codes.has('PROFIT_RISK')) return [
      '客户当前存在追加后毛利下滑风险，应列为高优先级健康干预。',
      '先推动补贴和低效消耗整改，并检查周报导入与结果回填。',
      '复核风险是否解除，再更新续费风险和下一步客户计划。',
    ]
    if (codes.has('BASIC_POOL')) return [
      '客户当前方案有破坏投放基本盘的风险，需要客户成功及时干预。',
      '把动作改为增量测试，并跟进客户是否完成执行与结果回填。',
      '实际 ROI 和毛利恢复后，再下调健康风险并复核续费状态。',
    ]
    if (!recommendation || !calculation) return [
      '客户周报口径尚未对齐，先完成数据干预，不生成收益预测。',
      '本周推动补齐归因定义、窗口和成熟周期，同时检查产品使用记录。',
      '数据可用后再评估经营健康，并安排续费风险复核。',
    ]
    return [
      '客户当前的健康风险主要在低效消耗和补贴，需要本周完成干预。',
      `建议${action}，把执行和复核记录留在客户健康档案里，降低续费风险。`,
      `下周重点看净 GMV 增加 ${calculation.deltaGmv} 元、毛利增加 ${calculation.deltaGrossProfit} 元的测算是否兑现。`,
    ]
  }
  if (codes.has('PROFIT_RISK')) return [
    '按当前假设，追加后毛利不升反降，本周先不加预算。',
    '先优化预算结构和商家补贴，保留当前方案作对照。',
    '等毛利测算转正并有基线证据后，再讨论追加。',
  ]
  if (codes.has('BASIC_POOL')) return [
    '保留现有工具基本盘，不做全量切换。',
    '只调整增量预算或小步测试，并保留本周方案作对照。',
    '实际 ROI 和毛利优于基线后，再决定是否扩大调整。',
  ]
  if (codes.has('ATTRIBUTION_IMMATURE')) return [
    '当前归因窗口尚未成熟，先不根据 ROI 排名调预算。',
    '等导出时间覆盖最后一条记录的完整归因窗口再复盘。',
    '本周只跟进已知消耗和过程事实，不做收益预测。',
  ]
  if (!recommendation || !calculation) return [
    '目前工具归因窗口不同，先统一归因定义和窗口再比较。',
    '本周先补齐同口径周报，不急着调整预算。',
    '数据对齐后再评估追加或挪移，避免看错投入回报。',
  ]
  return [
    `这周建议${action}，先把低效预算转到同口径高 ROI 工具。`,
    `按当前假设，净 GMV 预计增加 ${calculation.deltaGmv} 元，毛利预计增加 ${calculation.deltaGrossProfit} 元。`,
    '先执行一周并复核实际 ROI 和毛利，达到目标后再讨论是否继续加预算。',
  ]
}

function orderIssues(issues: DiagnosisIssue[], role: Role): DiagnosisIssue[] {
  const roleRank: Record<Role, Partial<Record<DiagnosisIssue['code'], number>>> = {
    ka: { BASIC_POOL: 1, LOW_ROI: 2, SUBSIDY: 3 },
    agency: { SUBSIDY: 1, LOW_ROI: 2, BASIC_POOL: 3 },
    cs: { SUBSIDY: 1, LOW_ROI: 2, BASIC_POOL: 3 },
  }
  return [...issues].sort((a, b) => {
    const aBlocked = a.code === 'ATTRIBUTION_MISMATCH' || a.code === 'ATTRIBUTION_IMMATURE' || a.code === 'PROFIT_RISK'
    const bBlocked = b.code === 'ATTRIBUTION_MISMATCH' || b.code === 'ATTRIBUTION_IMMATURE' || b.code === 'PROFIT_RISK'
    if (aBlocked !== bBlocked) return aBlocked ? -1 : 1
    return (roleRank[role][a.code] ?? 10) - (roleRank[role][b.code] ?? 10)
  })
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

  const orderedIssues = orderIssues(issues, role)
  return {
    issues: orderedIssues.slice(0, 3),
    recommendation,
    calculation,
    talkTracks: makeTalkTracks(recommendation, calculation, role, orderedIssues),
    followUps: makeFollowUps(report, recommendation, orderedIssues, role),
  }
}
