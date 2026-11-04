import type { DemoWeek } from '../domain/demoSeries'
import type { Calculation, Recommendation, ToolMetric, WeeklyReport } from '../domain/types'

const COLORS = ['#EA4335', '#34A853', '#4285F4', '#FBBC04', '#5F6368']

function compact(value: number): string {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1, notation: 'compact' }).format(value)
}

function money(value: number, signed = false): string {
  const prefix = signed && value > 0 ? '+' : value < 0 ? '-' : ''
  return `${prefix}¥${Math.abs(Math.round(value)).toLocaleString('zh-CN')}`
}

export function WeeklyTrend({ weeks }: { weeks: DemoWeek[] }) {
  if (!weeks.length) return null
  const width = 680
  const height = 250
  const left = 48
  const right = 18
  const top = 24
  const bottom = 42
  const chartHeight = height - top - bottom
  const chartWidth = width - left - right
  const maxGmv = Math.max(...weeks.map((week) => week.netGmv)) * 1.1
  const maxSpend = Math.max(...weeks.map((week) => week.spend)) * 2.8
  const maxRoi = Math.max(...weeks.map((week) => week.roi)) * 1.2
  const x = (index: number) => left + index * chartWidth / Math.max(1, weeks.length - 1)
  const y = (value: number, max: number) => top + chartHeight - value / max * chartHeight
  const gmvPoints = weeks.map((week, index) => `${x(index)},${y(week.netGmv, maxGmv)}`).join(' ')
  const roiPoints = weeks.map((week, index) => `${x(index)},${y(week.roi, maxRoi)}`).join(' ')
  return (
    <div className="weekly-trend chart-block">
      <div className="chart-legend" aria-label="图例">
        <span><i className="legend-blue" />净 GMV</span><span><i className="legend-yellow" />推广费</span><span><i className="legend-green" />整体推广 ROI</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="近 8 周净 GMV、推广费和整体推广 ROI 趋势">
        {[0, 1, 2, 3, 4].map((line) => {
          const lineY = top + line * chartHeight / 4
          return <g key={line}><line x1={left} x2={width - right} y1={lineY} y2={lineY} className="chart-gridline" /><text x={left - 8} y={lineY + 4} textAnchor="end" className="chart-axis-label">{compact(maxGmv * (4 - line) / 4)}</text></g>
        })}
        {weeks.map((week, index) => {
          const barHeight = top + chartHeight - y(week.spend, maxSpend)
          return <g key={week.weekStart}>
            <rect x={x(index) - 12} y={y(week.spend, maxSpend)} width="24" height={barHeight} rx="3" fill="#FBBC04" />
            <text x={x(index)} y={height - 16} textAnchor="middle" className="chart-axis-label">W{index + 1}</text>
          </g>
        })}
        <polyline points={gmvPoints} fill="none" stroke="#4285F4" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
        {weeks.map((week, index) => <circle key={`gmv-${week.weekStart}`} cx={x(index)} cy={y(week.netGmv, maxGmv)} r="4" fill="#4285F4" />)}
        <polyline points={roiPoints} fill="none" stroke="#34A853" strokeWidth="2" strokeDasharray="5 4" strokeLinejoin="round" />
        {weeks.map((week, index) => <circle key={`roi-${week.weekStart}`} cx={x(index)} cy={y(week.roi, maxRoi)} r="3" fill="#34A853" />)}
        <text x={x(weeks.length - 1)} y={y(weeks.at(-1)!.netGmv, maxGmv) - 10} textAnchor="end" className="chart-value-label blue">GMV {money(weeks.at(-1)!.netGmv)}</text>
        <text x={x(weeks.length - 1)} y={y(weeks.at(-1)!.roi, maxRoi) - 10} textAnchor="end" className="chart-value-label green">ROI {weeks.at(-1)!.roi}</text>
      </svg>
      <p className="chart-caption">合成演示序列 · 第 8 周与当前周报一致 · {weeks.at(-1)?.weekStart}</p>
    </div>
  )
}

export function ToolEfficiencyBars({ tools }: { tools: ToolMetric[] }) {
  const totalSpend = tools.reduce((sum, tool) => sum + tool.spend, 0)
  const minRoi = Math.min(...tools.map((tool) => tool.roi))
  return (
    <div className="tool-efficiency chart-block">
      {tools.map((tool, index) => {
        const share = totalSpend > 0 ? tool.spend / totalSpend : 0
        const low = tool.roi === minRoi
        return <div className="tool-efficiency-row" key={tool.toolName}>
          <div><strong>{tool.toolName}</strong><span className={low ? 'negative' : 'positive'}>ROI {tool.roi}{low ? ' · 最低' : ''}</span></div>
          <div className="tool-bar-line">
            <div className="bar-track" aria-hidden="true"><i style={{ width: `${share * 100}%`, background: low ? '#EA4335' : COLORS[(index + 1) % COLORS.length] }} /></div>
            <span>占 {(share * 100).toFixed(0)}% · {money(tool.spend)}</span>
          </div>
        </div>
      })}
      <p className="chart-caption">消耗占比看结构，ROI 看效率；只有同口径且归因成熟时才建议调预算。</p>
    </div>
  )
}

export function BudgetMix({ report, recommendation }: { report: WeeklyReport; recommendation: Recommendation }) {
  const proposed = report.tools.map((tool) => ({
    ...tool,
    spend: tool.spend + (recommendation.sourceTool === tool.toolName ? -recommendation.amount : recommendation.targetTool === tool.toolName ? recommendation.amount : 0),
  }))
  const currentTotal = report.tools.reduce((sum, tool) => sum + tool.spend, 0)
  const proposedTotal = proposed.reduce((sum, tool) => sum + tool.spend, 0)
  const row = (label: string, tools: ToolMetric[], total: number) => <div className="budget-mix-row">
    <span>{label}</span>
    <div className="budget-mix-bar" role="img" aria-label={`${label}预算 ${money(total)}`}>
      {tools.map((tool, index) => {
        const share = total > 0 ? tool.spend / total * 100 : 0
        return <i key={tool.toolName} style={{ width: `${share}%`, background: COLORS[index % COLORS.length] }} title={`${tool.toolName} ${money(tool.spend)}`}>{share >= 15 ? `${tool.toolName} ${Math.round(share)}%` : ''}</i>
      })}
    </div>
    <strong>{money(total)}</strong>
  </div>
  return (
    <div className="budget-mix chart-block">
      {row('现在', report.tools, currentTotal)}
      {row('建议', proposed, proposedTotal)}
      <ul className="budget-mix-values">
        {report.tools.map((tool) => <li key={tool.toolName}><span>{tool.toolName}</span><strong>{money(tool.spend)} → {money(proposed.find((item) => item.toolName === tool.toolName)?.spend ?? 0)}</strong></li>)}
      </ul>
    </div>
  )
}

export function ProfitWaterfall({ calculation }: { calculation: Calculation }) {
  const items = [
    { label: '预算结构贡献', value: calculation.budgetContribution ?? 0 },
    { label: '补贴变化贡献', value: calculation.subsidyContribution ?? 0 },
    { label: '订单流失影响', value: calculation.orderLossContribution ?? 0 },
  ]
  const width = 520
  const height = 250
  const top = 28
  const bottom = 56
  const chartHeight = height - top - bottom
  let running = 0
  const steps = items.map((item) => {
    const start = running
    running += item.value
    return { ...item, start, end: running }
  })
  const values = [0, calculation.deltaGrossProfit, ...steps.flatMap((step) => [step.start, step.end])]
  let min = Math.min(...values)
  let max = Math.max(...values)
  if (min === max) max = min + 1
  const padding = (max - min) * 0.15
  min -= padding
  max += padding
  const y = (value: number) => top + (max - value) / (max - min) * chartHeight
  const slot = width / 4
  const barWidth = 76
  return (
    <div className="profit-waterfall chart-block">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`调整毛利贡献拆解，净变化 ${money(calculation.deltaGrossProfit, true)}`}>
        <line x1="0" x2={width} y1={y(0)} y2={y(0)} className="chart-zero-line" />
        {steps.map((step, index) => {
          const x = index * slot + (slot - barWidth) / 2
          const topY = Math.min(y(step.start), y(step.end))
          const barHeight = Math.max(2, Math.abs(y(step.start) - y(step.end)))
          return <g key={step.label}>
            <rect x={x} y={topY} width={barWidth} height={barHeight} rx="4" fill={step.value > 0 ? '#34A853' : step.value < 0 ? '#EA4335' : '#DADCE0'} />
            <text x={x + barWidth / 2} y={Math.max(14, topY - 7)} textAnchor="middle" className={step.value < 0 ? 'chart-value-label red' : 'chart-value-label green'}>{money(step.value, true)}</text>
            <text x={x + barWidth / 2} y={height - 25} textAnchor="middle" className="chart-axis-label">{step.label}</text>
          </g>
        })}
        <rect x={3 * slot + (slot - barWidth) / 2} y={Math.min(y(0), y(calculation.deltaGrossProfit))} width={barWidth} height={Math.max(2, Math.abs(y(0) - y(calculation.deltaGrossProfit)))} rx="4" fill="#4285F4" />
        <text x={3 * slot + slot / 2} y={Math.max(14, Math.min(y(0), y(calculation.deltaGrossProfit)) - 7)} textAnchor="middle" className="chart-value-label blue">{money(calculation.deltaGrossProfit, true)}</text>
        <text x={3 * slot + slot / 2} y={height - 25} textAnchor="middle" className="chart-axis-label strong">净增毛利</text>
      </svg>
      <ul className="waterfall-values">
        {items.map((item) => <li key={item.label}><span>{item.label}</span><strong>{money(item.value, true)}</strong></li>)}
      </ul>
      <p className="chart-caption">贡献拆解与上方 GMV、毛利共用同一次测算；不是收益承诺。</p>
    </div>
  )
}
