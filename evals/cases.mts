import { controlCase, demoStore, mainCase, mainProductUsage } from '../src/domain/cases'
import { analyzeBusinessHealth } from '../src/domain/businessHealth'
import { cityProfiles, syntheticPeers } from '../src/domain/benchmarkCases'
import { buildDiagnosis, type Assumptions } from '../src/domain/diagnosis'
import { buildDataRequest, buildInitialObservations } from '../src/domain/intake'
import { buildRolePerspective } from '../src/domain/rolePerspective'
import { parseCsvWeeklyReport } from '../src/lib/weeklyReport'

export interface EvalCase {
  id: string
  group: string
  description: string
  check: () => { pass: boolean; evidence: string }
}

const assumptions: Assumptions = {
  mode: 'reallocate',
  amount: 400,
  grossMargin: 0.45,
  marginalFactor: 0.8,
  merchantSubsidyDelta: 0,
}

const csvHeader = '门店ID,周开始,订单,净GMV,商家补贴,平台补贴,投放工具,消耗,归因净GMV,归因窗口,归因定义,导出时间'
const validRow = 'S1,2026-10-12,1200,60000,4000,1500,点金推广,1000,10000,7,点击归因,2026-10-26T00:00:00+08:00'

export const evalCases: EvalCase[] = [
  {
    id: 'E-01', group: '历史方法', description: 'ROI 10 → ROI 18 小步挪移并同步计算毛利',
    check: () => {
      const result = buildDiagnosis(mainCase, assumptions)
      const pass = result.recommendation?.sourceTool === '点金推广'
        && result.recommendation.targetTool === '搜索推广'
        && result.calculation?.deltaGmv === 2560
        && result.calculation.deltaGrossProfit === 1152
      return { pass, evidence: JSON.stringify({ recommendation: result.recommendation, calculation: result.calculation }) }
    },
  },
  {
    id: 'E-02', group: '历史方法', description: '保留基本盘，不允许全量切换工具',
    check: () => {
      const result = buildDiagnosis(mainCase, { ...assumptions, amount: 1000 })
      const pass = result.recommendation === null && result.issues.some((issue) => issue.code === 'BASIC_POOL')
      return { pass, evidence: JSON.stringify({ recommendation: result.recommendation, issues: result.issues }) }
    },
  },
  {
    id: 'E-03', group: '历史方法', description: '追加后毛利为负时不鼓励追加预算',
    check: () => {
      const result = buildDiagnosis(mainCase, { ...assumptions, mode: 'add', grossMargin: 0.05 })
      const pass = result.recommendation === null && result.issues.some((issue) => issue.code === 'PROFIT_RISK')
      return { pass, evidence: JSON.stringify({ recommendation: result.recommendation, issues: result.issues }) }
    },
  },
  {
    id: 'E-04', group: '测算', description: '追加预算与预算内挪移分开扣除消耗',
    check: () => {
      const result = buildDiagnosis(mainCase, { ...assumptions, mode: 'add' })
      const pass = result.calculation?.deltaGmv === 5760 && result.calculation.deltaGrossProfit === 2192 && result.calculation.spendDelta === 400
      return { pass, evidence: JSON.stringify(result.calculation) }
    },
  },
  {
    id: 'E-05', group: '测算', description: '边际 ROI 假设变化会改变测算而不是硬编码结果',
    check: () => {
      const result = buildDiagnosis(mainCase, { ...assumptions, marginalFactor: 0.5 })
      const pass = result.calculation?.deltaGmv === 1600 && result.calculation.deltaGrossProfit === 720
      return { pass, evidence: JSON.stringify(result.calculation) }
    },
  },
  {
    id: 'E-06', group: '数据质量', description: '不同归因窗口不做排名或预算测算',
    check: () => {
      const result = buildDiagnosis(controlCase, assumptions)
      const pass = result.recommendation === null && result.calculation === null && result.issues.some((issue) => issue.code === 'ATTRIBUTION_MISMATCH')
      return { pass, evidence: JSON.stringify(result.issues) }
    },
  },
  {
    id: 'E-07', group: '数据质量', description: '归因窗口未成熟时阻断预算动作',
    check: () => {
      const result = buildDiagnosis({ ...mainCase, exportedAt: '2026-10-20T00:00:00+08:00' }, assumptions)
      const pass = result.recommendation === null && result.calculation === null && result.issues.some((issue) => issue.code === 'ATTRIBUTION_IMMATURE')
      return { pass, evidence: JSON.stringify(result.issues) }
    },
  },
  {
    id: 'E-08', group: '数据质量', description: '门店整体 GMV 不与工具归因 GMV 混加',
    check: () => {
      const result = buildDiagnosis(mainCase, assumptions)
      const pass = result.calculation?.currentGmv === 60000
      return { pass, evidence: `currentGmv=${result.calculation?.currentGmv}` }
    },
  },
  {
    id: 'E-09', group: '数据质量', description: '负数消耗在导入时被拒绝',
    check: () => {
      let message = ''
      try {
        parseCsvWeeklyReport(`${csvHeader}\n${validRow.replace(',1000,10000,', ',-1000,10000,')}`, demoStore)
      } catch (error) {
        message = error instanceof Error ? error.message : String(error)
      }
      return { pass: message.includes('不能为负'), evidence: message || '未拒绝负数消耗' }
    },
  },
  {
    id: 'E-10', group: '数据质量', description: '重复工具不双倍计算',
    check: () => {
      let message = ''
      try {
        parseCsvWeeklyReport(`${csvHeader}\n${validRow}\n${validRow}`, demoStore)
      } catch (error) {
        message = error instanceof Error ? error.message : String(error)
      }
      return { pass: message.includes('投放工具重复'), evidence: message }
    },
  },
  {
    id: 'E-11', group: '执行闭环', description: '每个行动都有负责人、复核指标、日期和停止条件',
    check: () => {
      const result = buildDiagnosis(mainCase, assumptions)
      const pass = result.followUps.every((item) => item.owner && item.metric && item.reviewDate
        && 'stopCondition' in item && String((item as unknown as Record<string, unknown>).stopCondition ?? '').length > 0)
      return { pass, evidence: JSON.stringify(result.followUps) }
    },
  },
  {
    id: 'E-12', group: '执行闭环', description: '复核保留基线或对照，不只看单次结果',
    check: () => {
      const result = buildDiagnosis(mainCase, assumptions)
      const text = result.followUps.map((item) => `${item.action}${item.target}`).join(' ')
      return { pass: text.includes('对照') || text.includes('基线'), evidence: text }
    },
  },
  {
    id: 'E-13', group: '输出与角色', description: '服务商和 SaaS 客户成功使用不同话术',
    check: () => {
      const agency = buildDiagnosis(mainCase, assumptions, 'agency').talkTracks.join(' ')
      const cs = buildDiagnosis(mainCase, assumptions, 'cs').talkTracks.join(' ')
      return { pass: agency.includes('新客户') && cs.includes('续费'), evidence: `${agency} | ${cs}` }
    },
  },
  {
    id: 'E-14', group: '输出与角色', description: '公开信息阶段不提前输出 ROI 结论',
    check: () => {
      const observations = buildInitialObservations(demoStore).join(' ')
      const request = buildDataRequest()
      const pass = !observations.includes('ROI') && request.files.length === 1
      return { pass, evidence: observations }
    },
  },
  {
    id: 'E-15', group: '输出与角色', description: '优先问题最多三个且每个都有数字',
    check: () => {
      const result = buildDiagnosis(mainCase, assumptions)
      const pass = result.issues.length <= 3 && result.issues.every((issue) => Number.isFinite(issue.value))
      return { pass, evidence: JSON.stringify(result.issues) }
    },
  },
  {
    id: 'E-16', group: '输出与角色', description: '话术不包含保证收益或必然因果',
    check: () => {
      const roles = ['ka', 'agency', 'cs'] as const
      const text = roles.flatMap((role) => buildDiagnosis(mainCase, assumptions, role).talkTracks).join(' ')
      const forbidden = ['保证收益', '必然增长', '一定赚钱', '证明工具更好'].filter((word) => text.includes(word))
      return { pass: forbidden.length === 0, evidence: forbidden.join('、') || '未命中禁用表达' }
    },
  },
  {
    id: 'E-17', group: '测算', description: '零调整金额不生成预算动作',
    check: () => {
      const result = buildDiagnosis(mainCase, { ...assumptions, amount: 0 })
      return { pass: result.recommendation === null && result.calculation === null, evidence: JSON.stringify(result.recommendation) }
    },
  },
  {
    id: 'E-18', group: '数据质量', description: '合成案例与真实导入保持不同数据标识',
    check: () => {
      const imported = parseCsvWeeklyReport(`${csvHeader}\n${validRow}`, demoStore)
      return { pass: mainCase.synthetic && !imported.synthetic, evidence: `main=${mainCase.synthetic}, imported=${imported.synthetic}` }
    },
  },
  {
    id: 'E-19', group: '数据质量', description: '数据索取清单覆盖全部导入必需字段',
    check: () => {
      const fields = buildDataRequest().fields
      const required = ['门店ID', '周开始', '订单', '净GMV', '投放工具', '消耗', '归因净GMV', 'ROI', '商家补贴', '导出时间']
      const missing = required.filter((field) => !fields.includes(field))
      return { pass: missing.length === 0, evidence: missing.length > 0 ? `缺少：${missing.join('、')}` : '必需字段齐全' }
    },
  },
  {
    id: 'E-20', group: '数据质量', description: '消耗为 0 但归因 GMV 大于 0 时拒绝导入',
    check: () => {
      let message = ''
      try {
        parseCsvWeeklyReport(`${csvHeader}\n${validRow.replace(',1000,10000,', ',0,10000,')}`, demoStore)
      } catch (error) {
        message = error instanceof Error ? error.message : String(error)
      }
      return { pass: message.includes('消耗为 0'), evidence: message || '未拒绝零消耗分母异常' }
    },
  },
  {
    id: 'E-21', group: '输出与角色', description: '角色改变问题优先级和跟进动作，不只改变话术',
    check: () => {
      const ka = buildDiagnosis(mainCase, assumptions, 'ka')
      const agency = buildDiagnosis(mainCase, assumptions, 'agency')
      const cs = buildDiagnosis(mainCase, assumptions, 'cs')
      const actions = new Set([ka.followUps[0].action, agency.followUps[0].action, cs.followUps[0].action])
      const pass = agency.issues[0].code === 'SUBSIDY' && ka.issues[0].code === 'LOW_ROI' && actions.size === 3
      return { pass, evidence: JSON.stringify({ ka: ka.issues, agency: agency.issues, actions: [...actions] }) }
    },
  },
  {
    id: 'E-22', group: '输出与角色', description: '角色化输出不修改共享预算测算',
    check: () => {
      const roles = ['ka', 'agency', 'cs'] as const
      const results = roles.map((role) => buildDiagnosis(mainCase, assumptions, role))
      const pass = results.every((result) => JSON.stringify(result.calculation) === JSON.stringify(results[0].calculation))
      return { pass, evidence: JSON.stringify(results.map((result) => result.calculation)) }
    },
  },
  {
    id: 'E-23', group: '输出与角色', description: '角色决策模块与六维优先级不同且共享事实不变',
    check: () => {
      const health = analyzeBusinessHealth(mainCase, syntheticPeers, cityProfiles)
      const diagnosis = buildDiagnosis(mainCase, assumptions, 'ka')
      const ka = buildRolePerspective('ka', mainCase, health, diagnosis, null)
      const agency = buildRolePerspective('agency', mainCase, health, diagnosis, null)
      const cs = buildRolePerspective('cs', mainCase, health, diagnosis, mainProductUsage)
      const facts = (perspective: typeof ka) => Object.fromEntries(perspective.dimensions.map((item) => [item.id, `${item.merchant}|${item.comparison}|${item.evidence}`]).sort(([a], [b]) => a.localeCompare(b)))
      const pass = new Set([ka.module.id, agency.module.id, cs.module.id]).size === 3
        && ka.dimensions[0].id !== agency.dimensions[0].id
        && ka.dimensions[0].id !== cs.dimensions[0].id
        && agency.dimensions[0].id !== cs.dimensions[0].id
        && JSON.stringify(facts(ka)) === JSON.stringify(facts(agency))
        && JSON.stringify(facts(ka)) === JSON.stringify(facts(cs))
      return { pass, evidence: JSON.stringify({ modules: [ka.module.id, agency.module.id, cs.module.id], first: [ka.dimensions[0].id, agency.dimensions[0].id, cs.dimensions[0].id] }) }
    },
  },
  {
    id: 'E-24', group: '输出与角色', description: 'SaaS 使用数据缺失时不生成续费风险等级',
    check: () => {
      const health = analyzeBusinessHealth(controlCase, syntheticPeers, cityProfiles)
      const diagnosis = buildDiagnosis(controlCase, assumptions, 'cs')
      const result = buildRolePerspective('cs', controlCase, health, diagnosis, null)
      const pass = result.usage.status === 'missing' && result.usage.riskLevel === null && result.metrics[1].value === '未提供'
      return { pass, evidence: JSON.stringify({ usage: result.usage, metric: result.metrics[1] }) }
    },
  },
]
