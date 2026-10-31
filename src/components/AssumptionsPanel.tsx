import type { Assumptions } from '../domain/diagnosis'

interface AssumptionsPanelProps {
  assumptions: Assumptions
  blocked: boolean
  error: string
  recalcMessage: string
  onChange: <K extends keyof Assumptions>(key: K, value: Assumptions[K]) => void
}

export function AssumptionsPanel({ assumptions, blocked, error, recalcMessage, onChange }: AssumptionsPanelProps) {
  return (
    <details className="assumptions-panel" open>
      <summary>
          <span>调整测算假设</span>
          <small>毛利率 {(assumptions.grossMargin * 100).toFixed(0)}% · 边际 ROI {(assumptions.marginalFactor * 100).toFixed(0)}% · {assumptions.amount} 元</small>
      </summary>
      <div className="assumptions-body">
        <p id="assumption-hint" className="assumption-hint">金额须为 1—1,000,000 元；预算内挪移须小于来源工具消耗。修改后，GMV、毛利和话术会同步重算。</p>
        {recalcMessage && <p className="recalc-message" role="status">{recalcMessage}</p>}
        {blocked && <p className="blocked-note"><strong>先统一归因口径，再谈预算</strong><span>当前只展示已知事实，不做 ROI 排名或收益测算。</span></p>}
        <label>调整方式
          <select name="budgetMode" autoComplete="off" value={assumptions.mode} onChange={(event) => onChange('mode', event.target.value as Assumptions['mode'])}>
            <option value="reallocate">预算内挪移</option><option value="add">追加预算</option>
          </select>
        </label>
        <label>调整金额（元）
          <input name="amount" autoComplete="off" inputMode="numeric" type="number" min="1" max="1000000" step="100" required aria-describedby="assumption-hint" aria-invalid={Boolean(error)} value={assumptions.amount} onChange={(event) => onChange('amount', Number(event.target.value))} />
        </label>
        <label>毛利率（%）
          <input name="grossMargin" autoComplete="off" inputMode="decimal" type="number" min="0" max="100" step="1" required value={assumptions.grossMargin * 100} onChange={(event) => onChange('grossMargin', Number(event.target.value) / 100)} />
        </label>
        <label>边际 ROI 折算（%）
          <input name="marginalFactor" autoComplete="off" inputMode="numeric" type="number" min="1" max="100" step="5" required value={assumptions.marginalFactor * 100} onChange={(event) => onChange('marginalFactor', Number(event.target.value) / 100)} />
        </label>
        <label>商家补贴变化（元）
          <input name="merchantSubsidyDelta" autoComplete="off" inputMode="numeric" type="number" min="-1000000" max="1000000" step="100" required value={assumptions.merchantSubsidyDelta} onChange={(event) => onChange('merchantSubsidyDelta', Number(event.target.value))} />
        </label>
        {error && <p className="error-message" role="alert">{error}</p>}
        <div className="formula-note">
          <strong>本页怎么算</strong>
          <p>{assumptions.mode === 'reallocate' ? '挪移不增加总消耗，只计算高低 ROI 工具的差额贡献。' : '追加预算会新增消耗，毛利测算同步扣除新增投放和补贴。'}</p>
        </div>
      </div>
    </details>
  )
}
