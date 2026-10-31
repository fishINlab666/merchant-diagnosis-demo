import { useMemo, useState } from 'react'
import './App.css'
import { controlCase, demoStore, mainCase } from './domain/cases'
import { buildDiagnosis, type Assumptions } from './domain/diagnosis'
import { buildDataRequest, buildInitialObservations } from './domain/intake'
import type { Role, StoreProfile, WeeklyReport } from './domain/types'
import { parseCsvWeeklyReport, parseXlsxWeeklyReport } from './lib/weeklyReport'
import { analyzeBusinessHealth } from './domain/businessHealth'
import { cityProfiles, syntheticPeers } from './domain/benchmarkCases'
import { AssumptionsPanel } from './components/AssumptionsPanel'
import { BusinessHealthView } from './components/BusinessHealthView'
import { ReportView } from './components/ReportView'

const dataRequest = buildDataRequest()
const roleNames: Record<Role, string> = { ka: '平台 KA', agency: '服务商', cs: 'SaaS 客户成功' }
const initialAssumptions: Assumptions = {
  mode: 'reallocate',
  amount: 400,
  grossMargin: 0.45,
  marginalFactor: 0.8,
  merchantSubsidyDelta: 0,
}

type UploadState = {
  status: 'idle' | 'ready' | 'parsing' | 'success' | 'error'
  message: string
}

function App() {
  const [store, setStore] = useState<StoreProfile>(demoStore)
  const [report, setReport] = useState<WeeklyReport | null>(mainCase)
  const [view, setView] = useState<'health' | 'budget'>('health')
  const [assumptions, setAssumptions] = useState<Assumptions>(initialAssumptions)
  const [role, setRole] = useState<Role>('ka')
  const [roleMessage, setRoleMessage] = useState('')
  const [activeStep, setActiveStep] = useState(3)
  const [file, setFile] = useState<File | null>(null)
  const [uploadState, setUploadState] = useState<UploadState>({ status: 'idle', message: '' })
  const [validationError, setValidationError] = useState('')
  const [recalcMessage, setRecalcMessage] = useState('')
  const result = useMemo(() => report ? buildDiagnosis(report, assumptions, role) : null, [report, assumptions, role])
  const healthAnalysis = useMemo(() => report ? analyzeBusinessHealth(report, syntheticPeers, cityProfiles) : null, [report])
  const observations = useMemo(() => buildInitialObservations(store), [store])
  const sourceSpend = useMemo(() => report ? Math.min(...report.tools.map((tool) => tool.spend)) : 0, [report])

  function updateStore<K extends keyof StoreProfile>(key: K, value: StoreProfile[K]) {
    setStore((current) => ({ ...current, [key]: value }))
  }

  function updateAssumptions<K extends keyof Assumptions>(key: K, value: Assumptions[K]) {
    const numericValue = Number(value)
    if (['amount', 'grossMargin', 'marginalFactor', 'merchantSubsidyDelta'].includes(key) && !Number.isFinite(numericValue)) {
      setValidationError('请输入有效数字，当前值未应用。')
      return
    }
    if (key === 'amount' && (numericValue < 1 || numericValue > 1000000)) {
      setValidationError('调整金额须为 1—1,000,000 元，当前值未应用。')
      return
    }
    if (key === 'amount' && assumptions.mode === 'reallocate' && report && numericValue >= sourceSpend) {
      setValidationError(`预算内挪移须小于来源工具消耗 ${sourceSpend} 元，以保留基本盘。`)
      return
    }
    if (key === 'grossMargin' && (numericValue < 0 || numericValue > 100)) {
      setValidationError('毛利率须为 0—100%，当前值未应用。')
      return
    }
    if (key === 'marginalFactor' && (numericValue < 1 || numericValue > 100)) {
      setValidationError('边际 ROI 折算须为 1—100%，当前值未应用。')
      return
    }
    if (key === 'merchantSubsidyDelta' && Math.abs(numericValue) > 1000000) {
      setValidationError('补贴变化的绝对值不能超过 1,000,000 元。')
      return
    }
    if (key === 'mode' && value === 'reallocate' && report && assumptions.amount >= sourceSpend) {
      setValidationError(`请先把调整金额降到 ${sourceSpend} 元以下，再切换为预算内挪移。`)
      return
    }
    setValidationError('')
    setAssumptions((current) => ({ ...current, [key]: value }))
    setRecalcMessage('假设已更新，报告已重算')
  }

  function changeRole(nextRole: Role) {
    setRole(nextRole)
    setRoleMessage(`已切换为 ${roleNames[nextRole]}版`)
  }

  function loadCase(selected: WeeklyReport) {
    setReport({ ...selected, store })
    setView('health')
    setActiveStep(3)
    setValidationError('')
    setRecalcMessage('')
    setUploadState({ status: 'idle', message: '' })
  }

  async function generateFromFile() {
    if (!file) return
    setUploadState({ status: 'parsing', message: `正在解析 ${file.name}…` })
    try {
      const parsed = file.name.toLowerCase().endsWith('.csv')
        ? parseCsvWeeklyReport(await file.text(), store)
        : await parseXlsxWeeklyReport(file, store)
      setReport(parsed)
      setView('health')
      setActiveStep(3)
      setValidationError('')
      setRecalcMessage('')
      setUploadState({ status: 'success', message: `周报解析成功：${parsed.tools.length} 个投放工具，已生成方案。` })
    } catch (cause) {
      const reason = cause instanceof Error ? cause.message : String(cause)
      setUploadState({ status: 'error', message: `解析失败：${reason}。请检查字段后重试。` })
    }
  }

  const canvas = report && result && healthAnalysis ? (
    <>
      <div className="view-tabs" role="tablist" aria-label="诊断视图">
        <button type="button" role="tab" id="health-tab" aria-controls="view-panel" aria-selected={view === 'health'} className={view === 'health' ? 'active' : ''} onClick={() => setView('health')}>经营全景</button>
        <button type="button" role="tab" id="budget-tab" aria-controls="view-panel" aria-selected={view === 'budget'} className={view === 'budget' ? 'active' : ''} onClick={() => setView('budget')}>预算方案</button>
      </div>
      <div id="view-panel" role="tabpanel" aria-labelledby={view === 'health' ? 'health-tab' : 'budget-tab'}>
        {view === 'health' ? (
          <BusinessHealthView report={report} analysis={healthAnalysis} peers={syntheticPeers} role={role} />
        ) : (
          <ReportView
            report={report}
            result={result}
            assumptions={assumptions}
            role={role}
            roleMessage={roleMessage}
            assumptionsPanel={<AssumptionsPanel
              assumptions={assumptions}
              blocked={!result.calculation}
              error={validationError}
              recalcMessage={recalcMessage}
              onChange={updateAssumptions}
            />}
          />
        )}
      </div>
    </>
  ) : null

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark">M</span>
          <div><strong>Merchant OS</strong><span>商户预算诊断</span></div>
        </div>
        <div className="header-actions">
          {report && <>
            <div className="role-switch" aria-label="报告角色">
              {(Object.keys(roleNames) as Role[]).map((item) => (
                <button type="button" key={item} aria-pressed={role === item} className={role === item ? 'active' : ''} onClick={() => changeRole(item)}>{roleNames[item]}</button>
              ))}
            </div>
            <button type="button" className="print-button" onClick={() => window.print()}>打印／保存 PDF</button>
          </>}
        </div>
      </header>

      <div className={`workspace ${report ? 'has-report' : ''}`}>
        {report && <main id="main-content" className="main-canvas">{canvas}</main>}
        <aside className="intake-sidebar">
          <div className="sidebar-heading">
            <p className="eyebrow">WORKFLOW</p>
            <h2>从信息到预算动作</h2>
          </div>
          <nav className="step-nav" aria-label="诊断步骤">
            {[['01', '公开信息'], ['02', '数据清单'], ['03', '预算方案']].map(([number, label], index) => (
              <button
                type="button"
                key={number}
                className={activeStep === index + 1 ? 'active' : ''}
                disabled={index === 2 && !report}
                title={index === 2 && !report ? '先加载主案例或上传周报，再打开预算方案' : `打开${label}`}
                aria-current={activeStep === index + 1 ? 'step' : undefined}
                onClick={() => index < 2 || report ? setActiveStep(index + 1) : undefined}
              >
                <span>{number}</span>{label}
              </button>
            ))}
          </nav>
          {!report && <p className="step-hint">第 3 步将在主案例或周报就绪后开放。</p>}

          <div className="intake-content">
            {activeStep === 1 && <>
              <div className="section-title"><span>STEP 01</span><h3>公开信息初诊</h3></div>
              <div className="form-grid">
                <label>商户别名<input name="merchantAlias" autoComplete="off" value={store.alias} onChange={(event) => updateStore('alias', event.target.value)} /></label>
                <label>平台<input name="platform" autoComplete="off" value={store.platform} onChange={(event) => updateStore('platform', event.target.value)} /></label>
                <label>城市／商圈<input name="city" autoComplete="off" value={store.city} onChange={(event) => updateStore('city', event.target.value)} /></label>
                <label>商圈<input name="district" autoComplete="off" value={store.district} onChange={(event) => updateStore('district', event.target.value)} /></label>
                <label>品类<input name="category" autoComplete="off" value={store.category} onChange={(event) => updateStore('category', event.target.value)} /></label>
                <label>价格带<input name="priceBand" autoComplete="off" value={store.priceBand} onChange={(event) => updateStore('priceBand', event.target.value)} /></label>
                <label>经营阶段<input name="stage" autoComplete="off" value={store.stage} onChange={(event) => updateStore('stage', event.target.value)} /></label>
                <label>公开评分<input name="rating" autoComplete="off" inputMode="decimal" type="number" min="0" max="5" step="0.1" value={store.rating} onChange={(event) => updateStore('rating', Number(event.target.value))} /></label>
                <label>公开菜品观察<textarea name="menuNote" autoComplete="off" rows={3} value={store.menuNote} onChange={(event) => updateStore('menuNote', event.target.value)} /></label>
              </div>
              <div className="observation-list">
                {observations.map((item) => <p key={item}>{item}</p>)}
              </div>
              <button type="button" className="primary-action" onClick={() => setActiveStep(2)}>生成数据清单</button>
            </>}

            {activeStep === 2 && <>
              <div className="section-title"><span>STEP 02</span><h3>只要一份周报</h3></div>
              <p className="request-file">{dataRequest.files[0]}</p>
              <div className="field-list">{dataRequest.fields.map((field) => <span key={field}>{field}</span>)}</div>
              <p className="optional-fields">可选经营字段：{dataRequest.optionalFields.join('、')}。缺省时对应分析显示“未提供”。</p>
              <ol className="export-steps">{dataRequest.exportSteps.map((step) => <li key={step}>{step}</li>)}</ol>
              <button type="button" className="text-action" onClick={() => setActiveStep(1)}>返回修改公开信息</button>
            </>}

            {activeStep === 3 && report && <>
              <div className="section-title"><span>STEP 03</span><h3>周报已就绪</h3></div>
              <dl className="report-meta">
                <div><dt>门店</dt><dd>{report.store.alias}</dd></div>
                <div><dt>周开始</dt><dd>{report.weekStart}</dd></div>
                <div><dt>投放工具</dt><dd>{report.tools.length} 个</dd></div>
              </dl>
              <button type="button" className="text-action" onClick={() => setActiveStep(1)}>返回修改门店信息</button>
            </>}
          </div>

          <div className="report-loader">
            <p className="loader-title">快速演示</p>
            <div className="case-buttons">
              <button type="button" onClick={() => loadCase(mainCase)}>加载主案例</button>
              <button type="button" onClick={() => loadCase(controlCase)}>加载对照案例</button>
            </div>
            <label className="file-label">上传周报<input name="weeklyReport" autoComplete="off" type="file" accept=".csv,.xlsx" onChange={(event) => {
              const selected = event.target.files?.[0] ?? null
              setFile(selected)
              setUploadState(selected ? { status: 'ready', message: `已选择 ${selected.name}，可以生成方案。` } : { status: 'idle', message: '' })
            }} /></label>
            <button type="button" className="primary-action" disabled={!file || uploadState.status === 'parsing'} onClick={() => void generateFromFile()}>
              {uploadState.status === 'parsing' ? '正在解析…' : '生成一页方案'}
            </button>
            {uploadState.message && <p className={`upload-status ${uploadState.status}`} role={uploadState.status === 'error' ? 'alert' : 'status'}>{uploadState.message}</p>}
          </div>
        </aside>
        {!report && <main id="main-content" className="main-canvas">{canvas}</main>}
      </div>
    </div>
  )
}

export default App
