import { useMemo, useState } from 'react'
import './App.css'
import { controlCase, demoStore, fineDiningCase, mainCase } from './domain/cases'
import { buildDiagnosis, type Assumptions } from './domain/diagnosis'
import { buildInitialObservations } from './domain/intake'
import { buildMerchantPerspective } from './domain/merchantPerspective'
import { searchPublicMerchant, type PublicSearchResult } from './domain/publicSearch'
import type { StoreProfile, WeeklyReport } from './domain/types'
import { parseCsvWeeklyReport, parseXlsxWeeklyReport, readCsvWeeklyReportHeaders, readXlsxWeeklyReportHeaders, readCsvWeeklyReportStoreId, readXlsxWeeklyReportStoreId } from './lib/weeklyReport'
import { buildHeaderMapping, evaluateHeaderMappings, type HeaderMappingPreview } from './lib/reportMapping'
import { analyzeBusinessHealth } from './domain/businessHealth'
import { cityProfiles, syntheticPeers } from './domain/benchmarkCases'
import { AssumptionsPanel } from './components/AssumptionsPanel'
import { BusinessHealthView } from './components/BusinessHealthView'
import { DemoWalkthrough } from './components/DemoWalkthrough'
import { HeaderMappingPreview as HeaderMappingPreviewView } from './components/HeaderMappingPreview'
import { MerchantIntake } from './components/MerchantIntake'
import { ReportView } from './components/ReportView'

const initialAssumptions: Assumptions = {
  mode: 'reallocate',
  amount: 400,
  grossMargin: 0.45,
  marginalFactor: 0.8,
  merchantSubsidyDelta: 0,
}

const blankStore: StoreProfile = {
  ...demoStore,
  alias: '',
  platform: '',
  city: '',
  district: '',
  category: '',
  priceBand: '',
  rating: Number.NaN,
  menuNote: '',
}

type UploadState = {
  status: 'idle' | 'ready' | 'parsing' | 'success' | 'error'
  message: string
}

function App() {
  const [store, setStore] = useState<StoreProfile>(blankStore)
  const [report, setReport] = useState<WeeklyReport | null>(null)
  const [stage, setStage] = useState<'intake' | 'public' | 'full'>('intake')
  const [demoMode, setDemoMode] = useState(false)
  const [view, setView] = useState<'health' | 'budget'>('health')
  const [publicResult, setPublicResult] = useState<PublicSearchResult | null>(null)
  const [searching, setSearching] = useState(false)
  const [assumptions, setAssumptions] = useState<Assumptions>(initialAssumptions)
  const [file, setFile] = useState<File | null>(null)
  const [mappingPreview, setMappingPreview] = useState<HeaderMappingPreview | null>(null)
  const [sourceStoreId, setSourceStoreId] = useState('')
  const [uploadState, setUploadState] = useState<UploadState>({ status: 'idle', message: '' })
  const [validationError, setValidationError] = useState('')
  const [recalcMessage, setRecalcMessage] = useState('')

  const result = useMemo(() => report ? buildDiagnosis(report, assumptions, 'ka') : null, [report, assumptions])
  const healthAnalysis = useMemo(() => report ? analyzeBusinessHealth(report, report.synthetic ? syntheticPeers : [], report.synthetic ? cityProfiles : []) : null, [report])
  const perspective = useMemo(() => report && result && healthAnalysis ? buildMerchantPerspective(report, healthAnalysis, result) : null, [report, result, healthAnalysis])
  const observations = useMemo(() => publicResult ? [...publicResult.observations, ...buildInitialObservations(store)] : [], [publicResult, store])
  const sourceSpend = useMemo(() => report ? Math.min(...report.tools.map((tool) => tool.spend)) : 0, [report])
  const identityMismatch = Boolean(sourceStoreId && store.storeId?.trim() && sourceStoreId !== store.storeId.trim())

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

  async function startDiagnosis() {
    if (!store.alias.trim() || searching) return
    setSearching(true)
    setUploadState({ status: 'idle', message: '' })
    const result = await searchPublicMerchant(store, fetch)
    setPublicResult(result)
    setStage('public')
    setSearching(false)
  }

  function generatePublicIntake() {
    setPublicResult({ status: 'manual', sources: [], observations: ['已根据人工补充信息生成公开初诊；以下仍需周报验证。'] })
    setStage('public')
  }

  async function changeFile(selected: File | null) {
    setFile(selected)
    setMappingPreview(null)
    setSourceStoreId('')
    if (!selected) {
      setUploadState({ status: 'idle', message: '' })
      return
    }
    setUploadState({ status: 'parsing', message: `正在读取 ${selected.name} 的表头…` })
    try {
      const headers = selected.name.toLowerCase().endsWith('.csv')
        ? readCsvWeeklyReportHeaders(await selected.text())
        : await readXlsxWeeklyReportHeaders(selected)
      const preview = buildHeaderMapping(headers)
      const fileStoreId = selected.name.toLowerCase().endsWith('.csv')
        ? readCsvWeeklyReportStoreId(await selected.text(), preview.mappings)
        : await readXlsxWeeklyReportStoreId(selected, preview.mappings)
      setSourceStoreId(fileStoreId)
      setMappingPreview(preview)
      setUploadState({
        status: preview.canGenerate ? 'ready' : 'error',
        message: preview.canGenerate ? '表头已读取，请确认映射后生成诊断。' : '存在缺失字段或重复映射，请修正文件后重新上传。',
      })
    } catch (cause) {
      const reason = cause instanceof Error ? cause.message : String(cause)
      setUploadState({ status: 'error', message: `表头读取失败：${reason}` })
    }
  }

  function changeMapping(index: number, standard: string | null) {
    setMappingPreview((current) => {
      if (!current) return current
      const next = evaluateHeaderMappings(current.mappings.map((item, itemIndex) => itemIndex === index ? { ...item, standard, match: 'manual' } : item))
      setUploadState({
        status: next.canGenerate ? 'ready' : 'error',
        message: next.canGenerate ? '映射已更新，请确认后生成诊断。' : '存在缺失字段或重复映射，请继续修正。',
      })
      return next
    })
  }

  function loadCase(selected: WeeklyReport) {
    setStore({ ...selected.store })
    setReport({ ...selected })
    setStage('full')
    setDemoMode(false)
    setView('health')
    setPublicResult(null)
    setValidationError('')
    setRecalcMessage('')
    setFile(null)
    setMappingPreview(null)
    setSourceStoreId('')
    setUploadState({ status: 'idle', message: '' })
  }

  function resetTool() {
    setStore(blankStore)
    setReport(null)
    setStage('intake')
    setDemoMode(false)
    setPublicResult(null)
    setFile(null)
    setMappingPreview(null)
    setSourceStoreId('')
    setUploadState({ status: 'idle', message: '' })
  }

  async function generateFromFile() {
    if (!file || !mappingPreview) return
    if (identityMismatch) {
      setUploadState({ status: 'error', message: `门店身份不一致：档案 ${store.storeId}，文件 ${sourceStoreId}。` })
      return
    }
    if (!mappingPreview.canGenerate) {
      setUploadState({ status: 'error', message: '请先修正缺失字段或重复映射，再生成诊断。' })
      return
    }
    setUploadState({ status: 'parsing', message: `正在按确认映射解析 ${file.name}…` })
    try {
      const parsed = file.name.toLowerCase().endsWith('.csv')
        ? parseCsvWeeklyReport(await file.text(), store, mappingPreview.mappings)
        : await parseXlsxWeeklyReport(file, store, mappingPreview.mappings)
      if (!store.storeId?.trim() && parsed.sourceStoreId) {
        setStore((current) => ({ ...current, storeId: parsed.sourceStoreId }))
      }
      setReport(parsed)
      setStage('full')
      setView('health')
      setValidationError('')
      setRecalcMessage('')
      setUploadState({ status: 'success', message: `周报解析成功：${parsed.tools.length} 个投放工具，已生成完整诊断。` })
    } catch (cause) {
      const reason = cause instanceof Error ? cause.message : String(cause)
      setUploadState({ status: 'error', message: `解析失败：${reason}。请检查字段后重试。` })
    }
  }

  const canvas = report && result && healthAnalysis && perspective ? (
    <>
      <div className="view-tabs" role="tablist" aria-label="诊断视图">
        <button type="button" role="tab" id="health-tab" aria-controls="view-panel" aria-selected={view === 'health'} className={view === 'health' ? 'active' : ''} onClick={() => setView('health')}>经营诊断</button>
        <button type="button" role="tab" id="budget-tab" aria-controls="view-panel" aria-selected={view === 'budget'} className={view === 'budget' ? 'active' : ''} onClick={() => setView('budget')}>行动方案</button>
      </div>
      <div id="view-panel" role="tabpanel" aria-labelledby={view === 'health' ? 'health-tab' : 'budget-tab'}>
        {view === 'health' ? (
          <BusinessHealthView report={report} analysis={healthAnalysis} peers={syntheticPeers} perspective={perspective} />
        ) : (
          <ReportView
            report={report}
            result={result}
            assumptions={assumptions}
            perspective={perspective}
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
          <div><strong>Merchant OS</strong><span>商家经营诊断</span></div>
        </div>
        <div className="header-actions">
          {report && <button type="button" className="print-button" onClick={() => window.print()}>打印／保存 PDF</button>}
        </div>
      </header>

      {stage !== 'full' ? (demoMode ? (
        <main id="main-content" className="main-canvas intake-main">
          <DemoWalkthrough report={mainCase} onComplete={() => loadCase(mainCase)} onExit={() => setDemoMode(false)} />
        </main>
      ) : (
        <main id="main-content" className="main-canvas intake-main">
          <MerchantIntake
            store={store}
            searching={searching}
            publicResult={publicResult}
            observations={observations}
            uploadState={uploadState}
            mappingPreview={mappingPreview}
            sourceStoreId={sourceStoreId}
            identityMismatch={identityMismatch}
            onMappingChange={changeMapping}
            onStoreChange={updateStore}
            onStart={() => void startDiagnosis()}
            onManual={generatePublicIntake}
            onFileChange={changeFile}
            onGenerate={() => void generateFromFile()}
            onStartDemo={() => setDemoMode(true)}
            onLoadCase={loadCase}
          />
        </main>
      )) : (
        <div className="workspace has-report">
          <main id="main-content" className="main-canvas">{canvas}</main>
          <aside className="intake-sidebar">
            <div className="sidebar-heading"><p className="eyebrow">WORKFLOW</p><h2>从店名到经营动作</h2></div>
            <nav className="step-nav" aria-label="诊断步骤">
              {[['01', '店名与公开信息'], ['02', '授权周报'], ['03', '经营诊断']].map(([number, label], index) => (
                <button type="button" key={number} className={index === 2 ? 'active' : ''} aria-current={index === 2 ? 'step' : undefined}><span>{number}</span>{label}</button>
              ))}
            </nav>
            <div className="intake-content">
              <div className="section-title"><span>STEP 03</span><h3>周报已就绪</h3></div>
              <dl className="report-meta">
                <div><dt>门店</dt><dd>{report?.store.alias}</dd></div>
                <div><dt>门店ID</dt><dd>{report?.sourceStoreId}</dd></div>
                <div><dt>品类</dt><dd>{report?.store.category || '未提供'}</dd></div>
                <div><dt>周开始</dt><dd>{report?.weekStart}</dd></div>
                <div><dt>投放工具</dt><dd>{report?.tools.length} 个</dd></div>
              </dl>
              <button type="button" className="text-action" onClick={resetTool}>诊断另一家门店</button>
            </div>
            <div className="report-loader">
              <p className="loader-title">换一份周报</p>
              <label className="file-label">上传周报<input name="weeklyReport" autoComplete="off" type="file" accept=".csv,.xlsx" onChange={(event) => void changeFile(event.target.files?.[0] ?? null)} /></label>
              {mappingPreview && <HeaderMappingPreviewView preview={mappingPreview} sourceStoreId={sourceStoreId} profileStoreId={store.storeId} identityMismatch={identityMismatch} onMappingChange={changeMapping} />}
              <button type="button" className="primary-action" disabled={!mappingPreview?.canGenerate || identityMismatch || uploadState.status === 'parsing'} onClick={() => void generateFromFile()}>{uploadState.status === 'parsing' ? '正在解析…' : '确认映射并生成诊断'}</button>
              {uploadState.message && <p className={`upload-status ${uploadState.status}`} role={uploadState.status === 'error' ? 'alert' : 'status'}>{uploadState.message}</p>}
              <p className="loader-title">试用其他合成示例</p>
              <div className="case-buttons">
                <button type="button" onClick={() => loadCase(mainCase)}>快餐示例</button>
                <button type="button" onClick={() => loadCase(fineDiningCase)}>正餐示例</button>
                <button type="button" onClick={() => loadCase(controlCase)}>归因异常示例</button>
              </div>
            </div>
          </aside>
        </div>
      )}
    </div>
  )
}

export default App
