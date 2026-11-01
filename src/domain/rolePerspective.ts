import type { BusinessDimension, BusinessHealthResult, CityStrategy } from './businessHealth'
import type { DiagnosisResult, ProductUsage, Role, WeeklyReport } from './types'

export interface RoleMetric {
  label: string
  value: string
  detail: string
}

export interface RoleDimension extends BusinessDimension {
  roleInsight: string
}

export interface RoleDecisionCard {
  label: string
  value: string
  detail: string
}

export interface RoleDecisionModule {
  id: 'jbp-budget' | 'acquisition-delivery' | 'health-renewal'
  title: string
  description: string
  cards: RoleDecisionCard[]
}

export interface RoleUsageView {
  status: 'available' | 'missing' | 'not-applicable'
  riskLevel: '高' | '中' | '低' | null
}

export interface RolePerspective {
  role: Role
  pageTitle: string
  decisionQuestion: string
  decisionSummary: string
  metrics: RoleMetric[]
  dimensions: RoleDimension[]
  module: RoleDecisionModule
  usage: RoleUsageView
  peerHeading: string
  peerDescription: string
  cityHeading: string
  cityDescription: string
  cityActions: Record<CityStrategy, string>
}

const dimensionOrder: Record<Role, BusinessDimension['id'][]> = {
  ka: ['commercial', 'subsidy', 'traffic', 'city', 'storefront', 'users'],
  agency: ['storefront', 'traffic', 'subsidy', 'users', 'commercial', 'city'],
  cs: ['users', 'subsidy', 'traffic', 'commercial', 'storefront', 'city'],
}

const roleInsights: Record<Role, Record<BusinessDimension['id'], string>> = {
  ka: {
    commercial: '决定增量预算和工具挪移',
    subsidy: '决定 JBP 先修利润还是扩量',
    traffic: '判断加曝光前是否先修承接',
    storefront: '作为预算沟通的基础证据',
    users: '决定老客运营是否纳入 JBP',
    city: '决定门店与城市资源分层',
  },
  agency: {
    commercial: '形成投放交付与复核证据',
    subsidy: '转成补贴与毛利复核服务',
    traffic: '转成可交付的转化优化动作',
    storefront: '把公开门店观察变成首聊钩子',
    users: '转成复购与会员运营服务',
    city: '用于多门店服务包分层',
  },
  cs: {
    commercial: '识别低效消耗并推动整改',
    subsidy: '识别经营健康恶化信号',
    traffic: '判断客户是否需要运营干预',
    storefront: '补足客户健康档案的基础风险',
    users: '识别留存风险并安排客户干预',
    city: '决定多门店客户干预顺序',
  },
}

function money(value: number): string {
  const formatted = Math.abs(Math.round(value)).toLocaleString('zh-CN')
  return value > 0 ? `+${formatted} 元` : value < 0 ? `-${formatted} 元` : '0 元'
}

function usageDepth(usage: ProductUsage): number {
  return [usage.activeOperators > 0, usage.reportImports > 0, usage.followUpCompletionRate >= 0.6].filter(Boolean).length
}

function riskLevel(riskSignals: number, usage: ProductUsage): '高' | '中' | '低' {
  if (usage.followUpCompletionRate < 0.5 && riskSignals > 0) return '高'
  if (riskSignals > 0 || usage.followUpCompletionRate < 0.8) return '中'
  return '低'
}

function recommendationText(diagnosis: DiagnosisResult): string {
  const recommendation = diagnosis.recommendation
  if (!recommendation) return '先统一数据口径'
  return recommendation.mode === 'reallocate'
    ? `从${recommendation.sourceTool}向${recommendation.targetTool}挪移 ${recommendation.amount} 元`
    : `向${recommendation.targetTool}追加 ${recommendation.amount} 元`
}

export function buildRolePerspective(
  role: Role,
  report: WeeklyReport,
  health: BusinessHealthResult,
  diagnosis: DiagnosisResult,
  productUsage: ProductUsage | null,
): RolePerspective {
  const byId = new Map(health.dimensions.map((item) => [item.id, item]))
  const dimensions = dimensionOrder[role].map((id) => ({
    ...byId.get(id)!,
    roleInsight: roleInsights[role][id],
  }))
  const riskSignals = health.dimensions.filter((item) => item.status === 'risk' || item.status === 'watch')
  const firstSignal = riskSignals[0] ?? health.dimensions[0]
  const reviewDate = diagnosis.followUps[0]?.reviewDate ?? report.weekStart
  const depth = productUsage ? usageDepth(productUsage) : 0
  const level = productUsage ? riskLevel(riskSignals.length, productUsage) : null
  const usage: RoleUsageView = role !== 'cs'
    ? { status: 'not-applicable', riskLevel: null }
    : productUsage ? { status: 'available', riskLevel: level } : { status: 'missing', riskLevel: null }
  const calculation = diagnosis.calculation
  const shared = {
    role,
    dimensions,
    usage,
    cityActions: role === 'ka' ? {
      scale: '优先测试增量预算', 'fix-funnel': '先修承接再投放', 'fix-profit': '先修毛利再扩量', 'fix-basics': '收回无效资源',
    } : role === 'agency' ? {
      scale: '交付扩量服务包', 'fix-funnel': '交付转化优化包', 'fix-profit': '交付毛利修复包', 'fix-basics': '交付门店基建包',
    } : {
      scale: '保持使用并复核扩量', 'fix-funnel': '安排转化干预', 'fix-profit': '安排毛利干预', 'fix-basics': '优先介入客户成功',
    },
  }

  if (role === 'ka') {
    return {
      ...shared,
      pageTitle: '经营全景',
      decisionQuestion: '本周预算怎么调，哪些门店值得加码？',
      decisionSummary: health.headline,
      metrics: [
        { label: '优先预算问题', value: `${diagnosis.issues.length} 项`, detail: '数据边界优先，最多保留三项' },
        { label: '预计净 GMV 变化', value: calculation ? money(calculation.deltaGmv) : '待统一口径', detail: '沿用当前测算假设' },
        { label: '预计毛利变化', value: calculation ? money(calculation.deltaGrossProfit) : '待统一口径', detail: '规模与利润一起进入 JBP' },
      ],
      module: {
        id: 'jbp-budget', title: 'JBP 与预算分层', description: '把经营差距转成预算、门店和城市资源决策。',
        cards: [
          { label: '钱漏在哪', value: diagnosis.issues[0]?.title ?? '未发现预算异常', detail: diagnosis.issues[0]?.detail ?? '保持当前口径复核' },
          { label: '预算动作', value: recommendationText(diagnosis), detail: calculation ? '保留基线并小步执行，不用单次 ROI 全量切换' : '归因不一致或未成熟时，不输出预算建议' },
          { label: '调整收益', value: calculation ? `净 GMV ${money(calculation.deltaGmv)} · 毛利 ${money(calculation.deltaGrossProfit)}` : '暂不测算', detail: calculation ? '与商家确认假设后进入 JBP 讨论' : '先补齐同口径周报' },
        ],
      },
      peerHeading: '竞店样本｜找预算差距', peerDescription: '用同口径样本定位可沟通的预算与补贴差距。',
      cityHeading: '城市分层｜决定资源加减', cityDescription: '按 UE 与增速决定加码、提效、修毛利或收回资源。',
    }
  }

  if (role === 'agency') {
    return {
      ...shared,
      pageTitle: '获客与交付全景',
      decisionQuestion: '用哪个问题开启沟通，本周交付什么？',
      decisionSummary: `以“${firstSignal.title}”作为首聊切口，再把诊断转成可验收的客户交付。`,
      metrics: [
        { label: '首聊服务切口', value: firstSignal.title, detail: `${firstSignal.merchant}，有证据再进入客户沟通` },
        { label: '本周交付动作', value: `${diagnosis.followUps.length} 项`, detail: '每项都有负责人、复核指标和停止条件' },
        { label: '客户复核日期', value: reviewDate, detail: '带着执行与前后数据复核，不只发报告' },
      ],
      module: {
        id: 'acquisition-delivery', title: '新客沟通与本周交付包', description: '把同一个诊断事实转成获客钩子、交付动作和客户案例证据。',
        cards: [
          { label: '首聊钩子', value: firstSignal.title, detail: `${firstSignal.merchant}；${firstSignal.comparison}` },
          { label: '本周交付包', value: `${diagnosis.followUps.length} 项运营动作`, detail: diagnosis.followUps.map((item) => item.action).join('；') },
          { label: '客户复核证据', value: calculation ? `GMV ${money(calculation.deltaGmv)} · 毛利 ${money(calculation.deltaGrossProfit)}` : '过程事实与执行记录', detail: '保留调整前后同口径数据；未执行不包装成客户案例' },
        ],
      },
      peerHeading: '竞店样本｜找服务切入点', peerDescription: '把本店与合格样本的差距转成客户能理解的交付问题。',
      cityHeading: '城市分层｜决定服务包分层', cityDescription: '不同门店匹配不同交付包，不用一套动作覆盖全部客户。',
    }
  }

  return {
    ...shared,
    pageTitle: '客户健康全景',
    decisionQuestion: '客户现在需要什么干预，何时复核续费风险？',
    decisionSummary: productUsage
      ? `发现 ${riskSignals.length} 项经营风险信号，结合产品使用深度安排客户干预。`
      : `发现 ${riskSignals.length} 项经营风险信号；缺少产品使用数据，暂不定续费风险等级。`,
    metrics: [
      { label: '经营风险信号', value: `${riskSignals.length} 项`, detail: riskSignals.map((item) => item.title).join('、') || '当前未命中风险或关注项' },
      { label: '产品使用深度', value: productUsage ? `${depth} / 3 核心行为` : '未提供', detail: productUsage ? '活跃、周报导入和结果回填分别检查' : '不能从 GMV 或 ROI 推断产品使用' },
      { label: '干预优先级', value: level ?? '待补数据', detail: level ? '规则化干预提醒，不是续费概率' : '补充使用行为后再判断' },
    ],
    module: {
      id: 'health-renewal', title: '客户健康与续费干预', description: '把经营风险和产品使用风险合并成客户成功行动，而非把经营下滑直接等同于流失。',
      cards: [
        { label: '经营健康', value: `${riskSignals.length} 项风险信号`, detail: riskSignals.map((item) => item.title).join('、') || '当前未命中风险或关注项' },
        productUsage ? {
          label: '产品使用深度', value: `${depth} / 3 核心行为`,
          detail: `活跃操作员 ${productUsage.activeOperators} 人 · 周报导入 ${productUsage.reportImports} 次 · 跟进回填 ${(productUsage.followUpCompletionRate * 100).toFixed(0)}% · 最近活跃 ${productUsage.lastActiveAt}`,
        } : { label: '产品使用深度', value: '未提供', detail: '补充产品使用数据后，才能判断使用不足与续费干预时机' },
        { label: '干预与续费复核', value: level ? `${level}优先级` : '先补使用数据', detail: productUsage ? `${productUsage.renewalReviewDate} 前复核风险是否解除；该等级只用于干预排序` : '当前只输出经营风险，不生成续费风险等级' },
      ],
    },
    peerHeading: '竞店样本｜识别健康偏差', peerDescription: '用同口径样本判断客户经营偏差，但不把偏差直接解释为续费结果。',
    cityHeading: '城市分层｜决定干预优先级', cityDescription: '按经营风险和门店类型安排客户成功干预顺序。',
  }
}
