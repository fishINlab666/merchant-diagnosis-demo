import type { BusinessHealthResult } from '../domain/businessHealth'
import { buildCustomerHealth } from '../domain/customerHealth'
import type { ProductUsage, WeeklyReport } from '../domain/types'

const riskLabels = { high: '高', medium: '中', low: '低', missing: '未评级' } as const

export function CustomerHealth({ report, health, usage }: { report: WeeklyReport; health: BusinessHealthResult; usage?: ProductUsage }) {
  const result = buildCustomerHealth(report, health, usage)
  return (
    <section className="customer-health role-special-module" aria-labelledby="customer-health-title">
      <div className="section-heading">
        <span className="section-number">03</span>
        <div><h2 id="customer-health-title">客户健康度与续费干预</h2><p>{report.synthetic ? '合成使用数据' : '授权经营数据'} · 健康度只表示干预优先级，不是续费概率。</p></div>
      </div>
      <div className="customer-health-layout">
        <div className={`health-gauge ${result.level}`}>
          <svg viewBox="0 0 240 145" role="img" aria-label={`客户健康度 ${result.score ?? '数据不足'}，${result.levelLabel}`}>
            <path d="M30 120 A90 90 0 0 1 210 120" fill="none" stroke="#E0E3E8" strokeWidth="18" strokeLinecap="round" />
            <path d="M30 120 A90 90 0 0 1 210 120" fill="none" stroke={result.level === 'red' ? '#EA4335' : result.level === 'yellow' ? '#FBBC04' : result.level === 'green' ? '#34A853' : '#DADCE0'} strokeWidth="18" strokeLinecap="round" pathLength="100" strokeDasharray={`${result.score ?? 0} 100`} />
            <text x="120" y="105" textAnchor="middle" className="health-score">{result.score ?? '--'}</text>
            <text x="120" y="132" textAnchor="middle" className="health-level">{result.levelLabel}</text>
          </svg>
          <details className="health-formula">
            <summary>健康分怎么算</summary>
            {result.deductions.length ? <ul>{result.deductions.map((item) => <li key={item}>{item}</li>)}</ul> : <p>缺少独立产品使用数据，不生成健康分。</p>}
            <p>基础分 100，按页面列出的信号扣分；只用于确定干预顺序。</p>
          </details>
        </div>
        <div className="health-signal-table-wrap">
          <table className="health-signal-table">
            <thead><tr><th>信号</th><th>现状</th><th>风险</th></tr></thead>
            <tbody>{result.signals.map((signal) => <tr key={signal.label}>
              <td data-label="信号">{signal.label}</td>
              <td data-label="现状">{signal.value}</td>
              <td data-label="风险"><span className={`health-risk ${signal.risk}`}>{riskLabels[signal.risk]}</span></td>
            </tr>)}</tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
