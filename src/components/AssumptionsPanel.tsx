import type { Assumptions } from '../domain/diagnosis'

interface AssumptionsPanelProps {
  assumptions: Assumptions
  blocked: boolean
  error: string
  recalcMessage: string
  onChange: <K extends keyof Assumptions>(key: K, value: Assumptions[K]) => void
}

interface NumberAssumptionProps {
  label: string
  name: string
  value: number
  min: number
  max: number
  step: number
  sliderMin?: number
  sliderMax?: number
  onChange: (value: number) => void
}

const sliderLabels: Record<string, string> = {
  amount: '预算金额滑块',
  grossMargin: '毛利率滑块',
  marginalFactor: '边际效率滑块',
  merchantSubsidyDelta: '补贴调整滑块',
  subsidyOrderLossRate: '补贴流失折算滑块',
}

function NumberAssumption({ label, name, value, min, max, step, sliderMin, sliderMax, onChange }: NumberAssumptionProps) {
  const rangeMin = sliderMin ?? min
  const rangeMax = sliderMax ?? max
  return (
    <div className="assumption-control">
      <label>{label}
        <input name={name} autoComplete="off" inputMode="numeric" type="number" min={min} max={max} step={step} required aria-describedby="assumption-hint" value={value} onChange={(event) => onChange(Number(event.target.value))} />
      </label>
      <input className="assumption-slider" aria-label={sliderLabels[name] ?? `${name} 滑块`} type="range" min={rangeMin} max={rangeMax} step={step} value={Math.min(rangeMax, Math.max(rangeMin, value))} onChange={(event) => onChange(Number(event.target.value))} />
    </div>
  )
}

export function AssumptionsPanel({ assumptions, blocked, error, recalcMessage, onChange }: AssumptionsPanelProps) {
  return (
    <details className="assumptions-panel" open>
      <summary>
        <span>调整测算假设</span>
        <small>{assumptions.period === 'month' ? '每月' : '每周'} · 毛利率 {(assumptions.grossMargin * 100).toFixed(0)}% · 边际 ROI {(assumptions.marginalFactor * 100).toFixed(0)}% · {assumptions.amount} 元</small>
      </summary>
      <div className="assumptions-body">
        <p id="assumption-hint" className="assumption-hint">滑块用于现场试算，数字框可输入完整范围。修改后，GMV、毛利、贡献拆解和话术会同步重算。</p>
        {recalcMessage && <p className="recalc-message" role="status">{recalcMessage}</p>}
        {blocked && <p className="blocked-note"><strong>先统一归因口径，再谈预算</strong><span>当前只展示已知事实，不做 ROI 排名或收益测算。</span></p>}
        <label>测算周期
          <select name="period" value={assumptions.period ?? 'week'} onChange={(event) => onChange('period', event.target.value as Assumptions['period'])}>
            <option value="week">单周</option><option value="month">每月（4.3 周）</option>
          </select>
        </label>
        <label>调整方式
          <select name="budgetMode" autoComplete="off" value={assumptions.mode} onChange={(event) => onChange('mode', event.target.value as Assumptions['mode'])}>
            <option value="reallocate">预算内挪移</option><option value="add">追加预算</option>
          </select>
        </label>
        <NumberAssumption label="调整金额（元）" name="amount" value={assumptions.amount} min={1} max={1000000} sliderMax={5000} step={100} onChange={(value) => onChange('amount', value)} />
        <NumberAssumption label="毛利率（%）" name="grossMargin" value={assumptions.grossMargin * 100} min={0} max={100} step={1} onChange={(value) => onChange('grossMargin', value / 100)} />
        <NumberAssumption label="边际 ROI 折算（%）" name="marginalFactor" value={assumptions.marginalFactor * 100} min={1} max={100} step={5} onChange={(value) => onChange('marginalFactor', value / 100)} />
        <NumberAssumption label="商家补贴变化（元）" name="merchantSubsidyDelta" value={assumptions.merchantSubsidyDelta} min={-1000000} max={1000000} sliderMin={-5000} sliderMax={5000} step={100} onChange={(value) => onChange('merchantSubsidyDelta', value)} />
        <NumberAssumption label="补贴收紧 GMV 流失折算（%）" name="subsidyOrderLossRate" value={(assumptions.subsidyOrderLossRate ?? 0.4) * 100} min={0} max={100} step={5} onChange={(value) => onChange('subsidyOrderLossRate', value / 100)} />
        {error && <p className="error-message" role="alert">{error}</p>}
        <div className="formula-note">
          <strong>本页怎么算</strong>
          <p>{assumptions.mode === 'reallocate' ? '挪移不增加总消耗，只计算高低 ROI 工具的差额贡献。' : '追加预算会新增消耗，毛利测算同步扣除新增投放和补贴。'} 补贴减少时，按流失折算扣除 GMV 和毛利；{assumptions.period === 'month' ? '月度按 4.3 周折算。' : '当前按单周计算。'}</p>
        </div>
      </div>
    </details>
  )
}
