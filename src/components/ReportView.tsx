import type { ReactNode } from 'react'
import type { Assumptions } from '../domain/diagnosis'
import type { RolePerspective } from '../domain/rolePerspective'
import type { DiagnosisResult, Role, WeeklyReport } from '../domain/types'
import { RoleDecisionPanel } from './RoleDecisionPanel'

const roleNames: Record<Role, string> = {
  ka: '平台 KA',
  agency: '服务商',
  cs: 'SaaS 客户成功',
}

const reportCopy = {
  ka: {
    title: '一页预算方案', stamp: '本周可执行', issue: '钱漏在哪', issueNote: '最多三个问题，每个都落到一笔钱或一个明确口径。',
    calculation: '调整前后算账', calculationNote: '按当前假设重算，门店整体与工具归因分开。',
    talk: '给老板的三句话', talkNote: '直接用于本周复盘会或预算沟通。', followUp: '下周 JBP 跟进表', followUpNote: '预算执行、责任和复核放在同一行。',
  },
  agency: {
    title: '一页客户交付方案', stamp: '本周可交付', issue: '客户最值得聊的问题', issueNote: '按获客与交付价值排序，每个问题都回到客户证据。',
    calculation: '交付方案调整前后算账', calculationNote: '共用同一测算，帮助客户理解交付动作的经营价值。',
    talk: '给客户的三句话', talkNote: '用于首聊、方案确认和下周客户复核。', followUp: '本周客户交付跟进表', followUpNote: '交付动作、负责人和客户复核证据放在同一行。',
  },
  cs: {
    title: '一页客户干预方案', stamp: '本周待干预', issue: '客户健康风险信号', issueNote: '按健康风险排序，不把经营下滑直接等同于续费结果。',
    calculation: '干预前后经营测算', calculationNote: '共用同一测算，复核干预是否改善经营结果。',
    talk: '客户干预的三句话', talkNote: '用于客户干预、使用推进和续费风险复核。', followUp: '干预与续费复核表', followUpNote: '经营干预、使用深度和续费复核放在同一行。',
  },
}

function money(value: number, signed = false): string {
  const formatted = new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    maximumFractionDigits: 0,
  }).format(Math.abs(value))
  if (signed && value > 0) return `+${formatted}`
  if (signed && value < 0) return `-${formatted}`
  return formatted
}

interface ReportViewProps {
  report: WeeklyReport
  result: DiagnosisResult
  assumptions: Assumptions
  perspective: RolePerspective
  roleMessage: string
  assumptionsPanel: ReactNode
}

export function ReportView({ report, result, assumptions, perspective, roleMessage, assumptionsPanel }: ReportViewProps) {
  const totalSpend = report.tools.reduce((sum, tool) => sum + tool.spend, 0)
  const { calculation } = result
  const role = perspective.role
  const copy = reportCopy[role]
  return (
    <article className={`report role-${role}`} aria-label={copy.title}>
      <header className="report-header">
        <div>
          <p className="eyebrow">{report.synthetic ? '合成演示数据' : '门店授权周报'} · {report.weekStart}</p>
          <h1>{copy.title}</h1>
          <p className="report-subtitle">{report.store.alias} · {report.store.category} · {roleNames[role]}版</p>
          {roleMessage && <p className="role-message" role="status">{roleMessage}</p>}
        </div>
        <div className="report-stamp">
          <span className="status-dot" aria-hidden="true" />
          {copy.stamp}
        </div>
      </header>

      <dl className="kpi-strip">
        <div><dt>门店订单</dt><dd>{report.orders.toLocaleString('zh-CN')}</dd></div>
        <div><dt>门店净 GMV</dt><dd>{money(report.netGmv)}</dd></div>
        <div><dt>投放消耗</dt><dd>{money(totalSpend)}</dd></div>
        <div><dt>商家补贴</dt><dd>{money(report.merchantSubsidy)}</dd></div>
      </dl>

      <RoleDecisionPanel perspective={perspective} context="budget" />

      <section className="report-section">
        <div className="section-heading">
          <span className="section-number">01</span>
          <div><h2>{copy.issue}</h2><p>{copy.issueNote}</p></div>
        </div>
        <div className="issue-grid">
          {result.issues.map((issue) => (
            <div className="issue" key={issue.code}>
              <p className="issue-title">{issue.title}</p>
              <p className="issue-value">{issue.code === 'ATTRIBUTION_MISMATCH'
                ? `${issue.value} 个工具`
                : issue.code === 'ATTRIBUTION_IMMATURE' ? `${issue.value} 天` : money(issue.value)}</p>
              <p className="issue-detail">{issue.detail}</p>
            </div>
          ))}
        </div>
      </section>

      {calculation && (
        <section className="report-section">
          <div className="section-heading">
            <span className="section-number">02</span>
            <div><h2>{copy.calculation}</h2><p>{copy.calculationNote}</p></div>
          </div>
          <div className="delta-row">
            <div><span>净 GMV 变化</span><strong>{money(calculation.deltaGmv, true)}</strong></div>
            <div><span>毛利变化</span><strong>{money(calculation.deltaGrossProfit, true)}</strong></div>
            <div><span>消耗变化</span><strong>{money(calculation.spendDelta, true)}</strong></div>
          </div>
          <table className="calculation-table">
            <thead><tr><th>指标</th><th>当前</th><th>建议方案</th></tr></thead>
            <tbody>
              <tr><th>门店净 GMV</th><td>{money(calculation.currentGmv)}</td><td>{money(calculation.projectedGmv)}</td></tr>
              <tr><th>经营毛利</th><td>{money(calculation.currentGrossProfit)}</td><td>{money(calculation.projectedGrossProfit)}</td></tr>
            </tbody>
          </table>
          <p className="assumption-note">测算假设：毛利率 {(assumptions.grossMargin * 100).toFixed(0)}% · 边际 ROI 折算 {(assumptions.marginalFactor * 100).toFixed(0)}% · 商家补贴变化 {money(assumptions.merchantSubsidyDelta)}</p>
        </section>
      )}

      {assumptionsPanel}

      <section className="report-section">
        <div className="section-heading">
          <span className="section-number">{calculation ? '03' : '02'}</span>
          <div><h2>{copy.talk}</h2><p>{copy.talkNote}</p></div>
        </div>
        <ol className="talk-list">
          {result.talkTracks.map((track, index) => <li key={track}><span>0{index + 1}</span><p>{track}</p></li>)}
        </ol>
      </section>

      <section className="report-section followup-section">
        <div className="section-heading">
          <span className="section-number">{calculation ? '04' : '03'}</span>
          <div><h2>{copy.followUp}</h2><p>{copy.followUpNote}</p></div>
        </div>
        <div className="table-scroll">
          <table className="followup-table">
            <thead><tr><th>动作</th><th>负责人</th><th>复核指标／目标</th><th>日期</th><th>实际结果</th></tr></thead>
            <tbody>{result.followUps.map((item, index) => (
              <tr key={item.action}>
                <td data-label="动作">{item.action}</td>
                <td data-label="负责人">{item.owner}</td>
                <td data-label="复核指标／目标">{item.metric}<br /><span>{item.target}</span><br /><span>停止：{item.stopCondition}</span></td>
                <td data-label="日期">{item.reviewDate}</td>
                <td data-label="实际结果"><input name={`followup-${index}`} autoComplete="off" aria-label={`${item.action}实际结果`} placeholder="待回填…" /></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </section>
    </article>
  )
}
