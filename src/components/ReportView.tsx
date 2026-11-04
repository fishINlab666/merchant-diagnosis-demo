import { useState, type ReactNode } from 'react'
import type { Assumptions } from '../domain/diagnosis'
import type { MerchantPerspective } from '../domain/merchantPerspective'
import type { DiagnosisResult, WeeklyReport } from '../domain/types'
import { BossQuestions } from './BossQuestions'
import { BudgetMix, ProfitWaterfall } from './Charts'

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
  perspective: MerchantPerspective
  assumptionsPanel: ReactNode
}

export function ReportView({ report, result, assumptions, perspective, assumptionsPanel }: ReportViewProps) {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'manual'>('idle')
  const totalSpend = report.tools.reduce((sum, tool) => sum + tool.spend, 0)
  const { calculation } = result
  const talkText = perspective.talkTracks.map((track, index) => `${index + 1}. ${track}`).join('\n')

  async function copyTalkTracks() {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('clipboard unavailable')
      await navigator.clipboard.writeText(talkText)
      setCopyState('copied')
    } catch {
      setCopyState('manual')
    }
  }

  return (
    <article className="report merchant-report" aria-label={perspective.reportTitle}>
      <header className="report-header">
        <div>
          <p className="eyebrow">{report.synthetic ? '合成演示数据' : '门店授权周报'} · {report.weekStart}</p>
          <h1>{perspective.reportTitle}</h1>
          <p className="report-subtitle">{report.store.alias} · {report.store.category} · 商家经营版</p>
        </div>
        <div className="report-stamp"><span className="status-dot" aria-hidden="true" />本周可执行</div>
      </header>

      <dl className="kpi-strip">
        <div><dt>门店订单</dt><dd>{report.orders.toLocaleString('zh-CN')}</dd></div>
        <div><dt>门店净 GMV</dt><dd>{money(report.netGmv)}</dd></div>
        <div><dt>投放消耗</dt><dd>{money(totalSpend)}</dd></div>
        <div><dt>商家补贴</dt><dd>{money(report.merchantSubsidy)}</dd></div>
      </dl>

      {calculation && result.recommendation && <section className="decision-summary" aria-label="本周预算决策">
        <div>
          <span>本周建议 · {result.recommendation.mode === 'reallocate' ? '总预算不变' : '小步追加'}</span>
          <h2>{result.recommendation.mode === 'reallocate' ? `从${result.recommendation.sourceTool}挪 ${result.recommendation.amount} 元到${result.recommendation.targetTool}` : `向${result.recommendation.targetTool}追加 ${result.recommendation.amount} 元`}</h2>
          <p>先执行一周并保留原方案作对照，实际 ROI 或毛利低于基线就回退。</p>
        </div>
        <div className="decision-profit"><span>{assumptions.period === 'month' ? '每月' : '每周'}预计净增毛利</span><strong>{money(calculation.deltaGrossProfit, true)}</strong><small>按当前假设测算，不是收益承诺</small></div>
      </section>}

      <section className="report-section">
        <div className="section-heading">
          <span className="section-number">01</span>
          <div><h2>钱漏在哪</h2><p>最多三个问题，每个都落到一笔钱或一个明确口径。</p></div>
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
            <div><h2>调整前后算账</h2><p>按当前假设重算，门店整体与工具归因分开；测算不是收益承诺。</p></div>
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
          <div className="scenario-visual-grid">
            {result.recommendation && <section>
              <div className="chart-panel-heading"><h3>预算怎么调</h3><p>对比现在与建议的工具预算结构。</p></div>
              <BudgetMix report={report} recommendation={result.recommendation} />
            </section>}
            <section>
              <div className="chart-panel-heading"><h3>调完能多赚多少</h3><p>毛利变化按贡献来源拆开。</p></div>
              <ProfitWaterfall calculation={calculation} />
            </section>
          </div>
          <p className="assumption-note">测算假设：{assumptions.period === 'month' ? '每月按 4.3 周' : '按单周'} · 毛利率 {(assumptions.grossMargin * 100).toFixed(0)}% · 边际 ROI 折算 {(assumptions.marginalFactor * 100).toFixed(0)}% · 商家补贴变化 {money(assumptions.merchantSubsidyDelta)} · 补贴收紧 GMV 流失折算 {((assumptions.subsidyOrderLossRate ?? 0.4) * 100).toFixed(0)}%</p>
        </section>
      )}

      {assumptionsPanel}

      <section className="report-section talk-section">
        <div className="section-heading">
          <span className="section-number">{calculation ? '03' : '02'}</span>
          <div><h2>给店里的三句话</h2><p>为什么调、怎么调、下周看什么。</p></div>
          <button type="button" className="secondary-action copy-talk-button" onClick={() => void copyTalkTracks()}>复制三句话</button>
        </div>
        <ol className="talk-list">
          {perspective.talkTracks.map((track, index) => <li key={track}><span>0{index + 1}</span><p>{track}</p></li>)}
        </ol>
        {copyState === 'copied' && <p className="copy-feedback" role="status">已复制，可以直接发给门店负责人。</p>}
        {copyState === 'manual' && <label className="manual-copy">手动复制三句话
          <textarea aria-label="手动复制三句话" readOnly rows={5} value={talkText} onFocus={(event) => event.currentTarget.select()} />
        </label>}
      </section>

      <section className="report-section followup-section">
        <div className="section-heading">
          <span className="section-number">{calculation ? '04' : '03'}</span>
          <div><h2>下周跟进表</h2><p>动作、负责人、复核指标和停止条件放在同一行。</p></div>
        </div>
        <div className="table-scroll">
          <table className="followup-table">
            <thead><tr><th>动作</th><th>负责人</th><th>复核指标／目标</th><th>日期</th><th>实际结果</th></tr></thead>
            <tbody>{perspective.followUps.map((item, index) => (
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

      <BossQuestions key={`${report.sourceStoreId}-${report.weekStart}-${report.exportedAt}-${JSON.stringify(assumptions)}`} report={report} result={result} assumptions={assumptions} />
    </article>
  )
}
