import { useEffect, useMemo, useState } from 'react'
import { analyzeBusinessHealth } from '../domain/businessHealth'
import { cityProfiles, syntheticPeers } from '../domain/benchmarkCases'
import { buildDiagnosis, type Assumptions } from '../domain/diagnosis'
import { buildDemoStages } from '../domain/demoWalkthrough'
import type { WeeklyReport } from '../domain/types'
import { buildHeaderMapping, type HeaderMappingPreview as HeaderMappingPreviewModel } from '../lib/reportMapping'
import { readCsvWeeklyReportHeaders } from '../lib/weeklyReport'
import { HeaderMappingPreview } from './HeaderMappingPreview'

const assumptions: Assumptions = {
  mode: 'reallocate',
  amount: 400,
  grossMargin: 0.45,
  marginalFactor: 0.8,
  merchantSubsidyDelta: 0,
}

interface DemoWalkthroughProps {
  report: WeeklyReport
  onComplete: () => void
  onExit: () => void
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function DemoWalkthrough({ report, onComplete, onExit }: DemoWalkthroughProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [mapping, setMapping] = useState<HeaderMappingPreviewModel | null>(null)
  const [mappingError, setMappingError] = useState('')
  const [running, setRunning] = useState(false)
  const [current, setCurrent] = useState(-1)
  const [completed, setCompleted] = useState(0)
  const [done, setDone] = useState(false)
  const diagnosis = useMemo(() => buildDiagnosis(report, assumptions, 'ka'), [report])
  const health = useMemo(() => analyzeBusinessHealth(report, syntheticPeers, cityProfiles), [report])
  const stages = useMemo(() => buildDemoStages(report, diagnosis, health), [report, diagnosis, health])

  useEffect(() => {
    let active = true
    void fetch('./fixtures/main-weekly.csv')
      .then((response) => {
        if (!response.ok) throw new Error(`示例周报读取失败（HTTP ${response.status}）`)
        return response.text()
      })
      .then((text) => {
        if (active) setMapping(buildHeaderMapping(readCsvWeeklyReportHeaders(text)))
      })
      .catch((error: unknown) => {
        if (active) setMappingError(error instanceof Error ? error.message : String(error))
      })
    return () => { active = false }
  }, [])

  async function runAnalysis() {
    if (running) return
    setRunning(true)
    setDone(false)
    setCompleted(0)
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    for (let index = 0; index < stages.length; index += 1) {
      setCurrent(index)
      await delay(reduced ? 0 : 550)
      setCompleted(index + 1)
    }
    setRunning(false)
    setDone(true)
  }

  return (
    <div className="demo-walkthrough">
      <nav className="demo-step-nav" aria-label="演示步骤">
        {['演示门店信息', '预填周报', '逐步分析', '分析结果'].map((label, index) => (
          <span className={step > index + 1 || (index === 3 && done) ? 'done' : step === index + 1 ? 'active' : ''} key={label}>0{index + 1} {label}</span>
        ))}
      </nav>

      {step === 1 && <section className="demo-panel">
        <p className="eyebrow">STEP 01 · 合成演示数据</p>
        <h1>演示门店信息</h1>
        <p className="demo-panel-intro">先确认这家店的公开档案。所有数据均为合成样本，用于展示分析方法，不代表真实商户成效。</p>
        <dl className="demo-profile-grid">
          <div><dt>店铺名称</dt><dd>{report.store.alias}</dd></div>
          <div><dt>门店 ID</dt><dd>{report.sourceStoreId}</dd></div>
          <div><dt>平台</dt><dd>{report.store.platform}</dd></div>
          <div><dt>城市／商圈</dt><dd>{report.store.city} · {report.store.district}</dd></div>
          <div><dt>品类／价格带</dt><dd>{report.store.category} · {report.store.priceBand}</dd></div>
          <div><dt>经营阶段</dt><dd>{report.store.stage}</dd></div>
          <div><dt>公开评分</dt><dd>{report.store.rating}</dd></div>
          <div><dt>菜单观察</dt><dd>{report.store.menuNote}</dd></div>
        </dl>
        <div className="demo-actions"><button type="button" className="text-action" onClick={onExit}>返回商家工具</button><button type="button" className="primary-action" onClick={() => setStep(2)}>下一步</button></div>
      </section>}

      {step === 2 && <section className="demo-panel">
        <p className="eyebrow">STEP 02 · 合成演示数据</p>
        <h1>预填周报与字段映射</h1>
        <p className="demo-panel-intro">已预填 `main-weekly.csv`，不需要上传文件。确认字段和门店身份后开始分析。</p>
        {mappingError && <p className="upload-status error" role="alert">{mappingError}</p>}
        {mapping && <HeaderMappingPreview preview={mapping} sourceStoreId={report.sourceStoreId} profileStoreId={report.store.storeId} />}
        <div className="demo-actions"><button type="button" className="text-action" onClick={() => setStep(1)}>上一步</button><button type="button" className="primary-action" disabled={!mapping?.canGenerate || running} onClick={() => { setStep(3); void runAnalysis() }}>开始分析</button></div>
      </section>}

      {step === 3 && <section className="demo-panel">
        <p className="eyebrow">STEP 03 · 本地规则与计算</p>
        <h1>逐步分析</h1>
        <p className="demo-panel-intro">每一步都显示真实计算证据；逐步揭示只是演示节奏，不代表云端 AI 作业。</p>
        <div className="demo-stage-list" aria-live="polite">
          {stages.map((stage, index) => {
            const complete = index < completed
            const active = running && index === current
            return <article className={`demo-stage ${complete ? 'complete' : active ? 'running' : 'pending'}`} key={stage.id}>
              <div className="demo-stage-status"><span>{complete ? '完成' : active ? '分析中' : '待分析'}</span><i /></div>
              <div><h2>{stage.title}</h2><p>{stage.description}</p>{(complete || active) && <strong>{stage.metric}</strong>}</div>
            </article>
          })}
        </div>
        {done && <div className="demo-analysis-complete" role="status"><strong>分析完成</strong><p>六个阶段均已完成，可以查看经营诊断与下周行动方案。</p></div>}
        <div className="demo-actions"><button type="button" className="text-action" disabled={running} onClick={() => setStep(2)}>返回映射</button>{done && <button type="button" className="primary-action" onClick={onComplete}>查看分析结果</button>}</div>
      </section>}
    </div>
  )
}
