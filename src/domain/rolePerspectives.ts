import type { BusinessDimension, BusinessHealthResult } from './businessHealth'
import { buildMerchantPerspective, type MerchantDimension, type MerchantPerspective } from './merchantPerspective'
import type { DiagnosisResult, Role, WeeklyReport } from './types'

export type DecisionRole = Extract<Role, 'merchant' | 'ka' | 'cs'>

const kaOrder: BusinessDimension['id'][] = ['commercial', 'subsidy', 'traffic', 'city', 'storefront', 'users']
const csOrder: BusinessDimension['id'][] = ['users', 'subsidy', 'traffic', 'commercial', 'storefront', 'city']

const kaInsights: Record<BusinessDimension['id'], string> = {
  commercial: '先用同口径效率确定预算调整空间',
  subsidy: '把补贴依赖转成 JBP 毛利约束',
  traffic: '判断追加预算前是否先修转化承接',
  city: '按增长与 UE 决定资源加码或收缩',
  storefront: '把评分、菜单和配送纳入商家执行项',
  users: '用复购和会员验证投入是否形成长期价值',
}

const csInsights: Record<BusinessDimension['id'], string> = {
  users: '优先确认留存与会员风险，不冒称续费因果',
  subsidy: '识别补贴依赖和毛利健康风险',
  traffic: '定位客户经营漏斗需要干预的环节',
  commercial: '确认客户花钱能否看到可复核回报',
  storefront: '把门店基建问题转成客户干预任务',
  city: '只在有同口径样本时判断客户所处位置',
}

function reorder(
  dimensions: MerchantDimension[],
  order: BusinessDimension['id'][],
  insights: Record<BusinessDimension['id'], string>,
): MerchantDimension[] {
  const byId = new Map(dimensions.map((item) => [item.id, item]))
  return order.map((id) => ({ ...byId.get(id)!, decisionInsight: insights[id] }))
}

function money(value: number): string {
  return `${Math.round(value).toLocaleString('zh-CN')} 元`
}

export function buildRolePerspective(
  role: DecisionRole,
  report: WeeklyReport,
  health: BusinessHealthResult,
  diagnosis: DiagnosisResult,
): MerchantPerspective {
  const base = buildMerchantPerspective(report, health, diagnosis)
  if (role === 'merchant') return { ...base, role }
  const calculation = diagnosis.calculation
  const recommendation = diagnosis.recommendation
  if (role === 'ka') {
    const scaleCount = health.cities.filter((city) => city.strategy === 'scale').length
    return {
      ...base,
      role,
      pageTitle: '平台 KA 经营诊断',
      reportTitle: '预算调整与 JBP 方案',
      decisionQuestion: '预算先怎么调，下一步 JBP 怎么谈？',
      decisionSummary: '先用同口径 ROI 和毛利证据修复结构，再按城市／门店分层配置资源。',
      metrics: [
        { label: '预算动作', value: recommendation ? `${money(recommendation.amount)}` : '暂不调整', detail: recommendation ? `${recommendation.sourceTool ?? '增量预算'} → ${recommendation.targetTool}` : '先修复归因或毛利风险' },
        { label: '测算毛利变化', value: calculation ? money(calculation.deltaGrossProfit) : '暂不测算', detail: '与老板版共用同一份假设和计算' },
        { label: '城市样本', value: `${health.cities.length} 个`, detail: health.cities.length ? `${scaleCount} 个建议优先加码` : '未提供同口径城市样本' },
      ],
      dimensions: reorder(base.dimensions, kaOrder, kaInsights),
      module: {
        id: 'ka-jbp',
        title: 'JBP 与预算分层',
        description: '把预算动作、经营证据和城市资源决策放在同一页，服务复盘会和 JBP 沟通。',
        cards: [
          { label: '预算动作', value: base.module.cards[1].value, detail: '先小步执行并保留基线，不用单次 ROI 排名直接追加。' },
          { label: 'JBP 证据', value: calculation ? `毛利 ${money(calculation.deltaGrossProfit)}` : '先统一数据口径', detail: calculation ? `净 GMV 变化 ${money(calculation.deltaGmv)}，按当前假设测算` : '口径未通过时不输出收益预测' },
          { label: '资源分层', value: health.cities.length ? `${scaleCount} 个城市优先加码` : '城市样本未提供', detail: '按增长 × UE 决定加码、稳住、调结构或收缩整改。' },
        ],
      },
      followUps: diagnosis.followUps,
      talkTracks: diagnosis.talkTracks,
    }
  }
  return {
    ...base,
    role,
    pageTitle: '客户健康诊断',
    reportTitle: '客户健康与续费干预方案',
    decisionQuestion: '客户风险在哪里，本周先干预什么？',
    decisionSummary: '经营风险与产品使用信号分开核验；健康度只表示干预优先级，不是续费概率。',
    metrics: [
      { label: '经营风险', value: `${diagnosis.issues.length} 项`, detail: diagnosis.issues[0]?.title ?? '当前未发现明确异常' },
      { label: '产品使用', value: '未提供', detail: '使用行为独立输入，不从 GMV 或 ROI 推断' },
      { label: '续费复核', value: '未提供', detail: '没有合同或复核日期时不生成续费窗口' },
    ],
    dimensions: reorder(base.dimensions, csOrder, csInsights),
    module: {
      id: 'cs-health',
      title: '客户健康与续费干预',
      description: '同时呈现经营风险、产品使用深度和复核动作；缺数据就关闭评分，不做续费预测。',
      cards: [
        { label: '经营风险', value: diagnosis.issues[0]?.title ?? '未发现明确异常', detail: diagnosis.issues[0]?.detail ?? '按当前证据保持复核' },
        { label: '使用深度', value: '使用数据未提供', detail: '需要周报导入、跟进回填、活跃操作员和最近活跃日期。' },
        { label: '干预复核', value: diagnosis.followUps[0]?.reviewDate ?? '待确认', detail: diagnosis.followUps[0]?.stopCondition ?? '客户确认前先补齐证据' },
      ],
    },
    followUps: diagnosis.followUps,
    talkTracks: diagnosis.talkTracks,
  }
}
