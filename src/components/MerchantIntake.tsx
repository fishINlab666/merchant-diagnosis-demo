import type { PublicSearchResult } from '../domain/publicSearch'
import type { StoreProfile, WeeklyReport } from '../domain/types'
import type { HeaderMappingPreview as HeaderMappingPreviewModel } from '../lib/reportMapping'
import { controlCase, fineDiningCase, mainCase } from '../domain/cases'
import { HeaderMappingPreview } from './HeaderMappingPreview'

interface UploadState {
  status: 'idle' | 'ready' | 'parsing' | 'success' | 'error'
  message: string
}

interface MerchantIntakeProps {
  store: StoreProfile
  searching: boolean
  publicResult: PublicSearchResult | null
  observations: string[]
  uploadState: UploadState
  mappingPreview: HeaderMappingPreviewModel | null
  onMappingChange: (index: number, standard: string | null) => void
  onStoreChange: <K extends keyof StoreProfile>(key: K, value: StoreProfile[K]) => void
  onStart: () => void
  onManual: () => void
  onFileChange: (file: File | null) => void
  onGenerate: () => void
  onLoadCase: (report: WeeklyReport) => void
}

export function MerchantIntake({
  store,
  searching,
  publicResult,
  observations,
  uploadState,
  mappingPreview,
  onMappingChange,
  onStoreChange,
  onStart,
  onManual,
  onFileChange,
  onGenerate,
  onLoadCase,
}: MerchantIntakeProps) {
  return (
    <div className="merchant-intake">
      <section className="intake-hero">
        <p className="eyebrow">MERCHANT DIAGNOSIS · 商家自助工具</p>
        <h1>输入店名，开始经营诊断</h1>
        <p>公开信息初诊 → 一份周报完整诊断 → 下周行动方案。公开信息不足时会明确降级，不用店名编造成绩。</p>
      </section>

      <section className="intake-card" aria-label="门店档案">
        <div className="intake-form-grid">
          <label>店铺名称<input name="shopName" autoComplete="off" required value={store.alias} placeholder="例如：张记煲仔饭（城西店）" onChange={(event) => onStoreChange('alias', event.target.value)} /></label>
          <label>平台<input name="platform" autoComplete="off" value={store.platform} placeholder="例如：美团／饿了么" onChange={(event) => onStoreChange('platform', event.target.value)} /></label>
          <label>城市<input name="city" autoComplete="off" value={store.city} placeholder="用于缩小公开检索范围" onChange={(event) => onStoreChange('city', event.target.value)} /></label>
          <label>商圈<input name="district" autoComplete="off" value={store.district} placeholder="例如：城西科创商圈" onChange={(event) => onStoreChange('district', event.target.value)} /></label>
          <label>品类<input name="category" autoComplete="off" value={store.category} placeholder="例如：中式快餐" onChange={(event) => onStoreChange('category', event.target.value)} /></label>
          <label>价格带<input name="priceBand" autoComplete="off" value={store.priceBand} placeholder="例如：25—35 元" onChange={(event) => onStoreChange('priceBand', event.target.value)} /></label>
        </div>

        <details className="public-fields" open={Boolean(publicResult)}>
          <summary>补充公开信息（可选，用于人工确认）</summary>
          <div className="intake-form-grid">
            <label>公开评分<input name="rating" autoComplete="off" inputMode="decimal" type="number" min="0" max="5" step="0.1" value={Number.isFinite(store.rating) ? store.rating : ''} onChange={(event) => onStoreChange('rating', event.target.value === '' ? Number.NaN : Number(event.target.value))} /></label>
            <label>经营阶段<input name="stage" autoComplete="off" value={store.stage} onChange={(event) => onStoreChange('stage', event.target.value)} /></label>
            <label className="field-wide">公开菜品观察<textarea name="menuNote" autoComplete="off" rows={3} value={store.menuNote} placeholder="套餐、价格、招牌菜、典型评价等" onChange={(event) => onStoreChange('menuNote', event.target.value)} /></label>
          </div>
        </details>

        <button type="button" className="primary-action intake-start" disabled={!store.alias.trim() || searching} onClick={onStart}>
          {searching ? '正在检索公开信息…' : '开始经营诊断'}
        </button>
      </section>

      {publicResult && <section className="public-intake-result" aria-labelledby="public-intake-title">
        <div className="section-heading">
          <div><h2 id="public-intake-title">公开信息初诊</h2><p>事实、待确认信息和下一步数据边界分开呈现。</p></div>
        </div>
        {publicResult.error && <p className="upload-status error" role="alert">公开检索失败：{publicResult.error}</p>}
        <div className="observation-list">
          {observations.map((item, index) => <p key={`${index}-${item}`}>{item}</p>)}
        </div>
        {publicResult.sources.length > 0 && <div className="public-sources">
          <strong>公开来源</strong>
          {publicResult.sources.map((source) => <details key={source.url}>
            <summary>{source.title}</summary>
            <p>采集时间：{source.capturedAt}</p>
            <p>{source.snippet}</p>
            <a href={source.url} target="_blank" rel="noreferrer">打开公开搜索来源</a>
          </details>)}
        </div>}
        <button type="button" className="text-action" onClick={onManual}>生成公开初诊</button>
      </section>}

      {publicResult && <section className="intake-card weekly-upload">
        <div className="section-heading">
          <div><h2>上传一份周报，生成完整诊断</h2><p>CSV／XLSX 只在本机解析，不发送给公开检索服务。</p></div>
        </div>
        <label className="file-label">上传周报<input name="weeklyReport" autoComplete="off" type="file" accept=".csv,.xlsx" onChange={(event) => onFileChange(event.target.files?.[0] ?? null)} /></label>
        {mappingPreview && <HeaderMappingPreview preview={mappingPreview} onMappingChange={onMappingChange} />}
        <button type="button" className="primary-action" disabled={!mappingPreview?.canGenerate || uploadState.status === 'parsing'} onClick={onGenerate}>
          {uploadState.status === 'parsing' ? '正在解析…' : '确认映射并生成诊断'}
        </button>
        {uploadState.message && <p className={`upload-status ${uploadState.status}`} role={uploadState.status === 'error' ? 'alert' : 'status'}>{uploadState.message}</p>}
      </section>}

      <section className="demo-cases" aria-label="试用示例">
        <span>没有现成周报？试用合成示例</span>
        <div className="case-buttons">
          <button type="button" onClick={() => onLoadCase(mainCase)}>快餐示例</button>
          <button type="button" onClick={() => onLoadCase(fineDiningCase)}>正餐示例</button>
          <button type="button" onClick={() => onLoadCase(controlCase)}>归因异常示例</button>
        </div>
      </section>
    </div>
  )
}
