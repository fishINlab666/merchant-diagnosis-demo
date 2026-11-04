import type { PublicIntakeAnalysis } from '../domain/intake'

interface PublicIntakeViewProps {
  text: string
  analysis: PublicIntakeAnalysis | null
  onTextChange: (text: string) => void
  onAnalyze: () => void
  onFillSample: () => void
}

function value(content: string | number | null, suffix = ''): string {
  return content === null || content === '' ? '未提供' : `${content}${suffix}`
}

export function PublicIntakeView({ text, analysis, onTextChange, onAnalyze, onFillSample }: PublicIntakeViewProps) {
  return (
    <>
      <section className="public-paste-panel" aria-labelledby="public-paste-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">PUBLIC INTAKE · 无需授权</p>
            <h2 id="public-paste-title">粘贴店铺页，先找候选问题</h2>
            <p>从外卖店铺页复制评分、月售、价格、菜单和评价。竞店只有明确粘贴后才参与对比。</p>
          </div>
        </div>
        <label className="field-wide">店铺页公开信息
          <textarea
            name="publicShopText"
            rows={7}
            value={text}
            placeholder={'例如：\n评分 4.4 · 月售 2600+ · 人均 ¥29 · 配送约 42 分钟\n评价：\n“配送太慢，送到饭都凉了”\n竞店：某餐厅｜评分 4.7｜配送约 31 分钟'}
            onChange={(event) => onTextChange(event.target.value)}
          />
        </label>
        <div className="public-paste-actions">
          <button type="button" className="secondary-action" onClick={onFillSample}>填入合成店铺页示例</button>
          <button type="button" className="primary-action" disabled={!text.trim()} onClick={onAnalyze}>提取公开信息并初诊</button>
        </div>
      </section>

      {analysis && <section className="public-intake-result" aria-labelledby="public-intake-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">STEP 01 · 公开事实与待验证问题</p>
            <h2 id="public-intake-title">公开信息初诊</h2>
            <p>{analysis.facts.name || '未命名门店'} · 只呈现粘贴证据，不推断投放或利润。</p>
          </div>
          <span className="status-badge info">初诊</span>
        </div>

        <dl className="public-fact-grid">
          <div><dt>公开评分</dt><dd>{value(analysis.facts.rating)}</dd></div>
          <div><dt>月售</dt><dd>{analysis.facts.monthlySales === null ? '未提供' : `${analysis.facts.monthlySales}+`}</dd></div>
          <div><dt>人均</dt><dd>{value(analysis.facts.averagePrice, ' 元')}</dd></div>
          <div><dt>配送时长</dt><dd>{value(analysis.facts.deliveryMinutes, ' 分钟')}</dd></div>
        </dl>

        <div className="public-analysis-grid">
          <section>
            <h3>差评主题与原文</h3>
            {analysis.themes.length ? <div className="review-theme-list">
              {analysis.themes.map((theme) => <article className="review-theme" key={theme.id}>
                <div><strong>{theme.label}</strong><span>{theme.count} 条</span></div>
                {theme.quotes.slice(0, 2).map((quote) => <blockquote key={quote}>“{quote}”</blockquote>)}
              </article>)}
            </div> : <p className="empty-evidence">未识别到评价原文，请补充典型好评和差评。</p>}
          </section>

          <section className="public-comparison">
            <h3>竞店公开对比</h3>
            {analysis.competitors.length ? <div className="competitor-list">
              <div className="competitor-row current"><strong>本店</strong><span>评分 {value(analysis.facts.rating)}</span><span>配送 {value(analysis.facts.deliveryMinutes, ' 分钟')}</span></div>
              {analysis.competitors.map((peer) => <div className="competitor-row" key={peer.name}>
                <strong>{peer.name}</strong><span>评分 {value(peer.rating)}</span><span>配送 {value(peer.deliveryMinutes, ' 分钟')}</span>
              </div>)}
              {analysis.peerSummary && <p className="evidence-note">仅基于上方 {analysis.competitors.length} 家粘贴竞店：评分中位数 {value(analysis.peerSummary.ratingMedian)}，配送中位数 {value(analysis.peerSummary.deliveryMinutesMedian, ' 分钟')}。</p>}
            </div> : <p className="empty-evidence">尚未粘贴竞店，不生成“商圈均值”或排名。</p>}
          </section>
        </div>

        <section className="public-candidates">
          <div className="section-heading"><div><h3>最值得先核查的地方</h3><p>每条都是候选问题，不是已经证实的经营结论。</p></div></div>
          {analysis.candidates.length ? analysis.candidates.map((candidate, index) => <article className="public-candidate" key={candidate.title}>
            <span className="candidate-number">0{index + 1}</span>
            <div>
              <h4>{candidate.title}</h4>
              <p className="candidate-evidence">{candidate.evidence}</p>
              <p>{candidate.hypothesis}</p>
              <strong>{candidate.action}</strong>
              {candidate.quote && <blockquote>“{candidate.quote}”</blockquote>}
            </div>
          </article>) : <p className="empty-evidence">只有店名还不足以形成初诊。请补充评分、配送、菜单或评价原文。</p>}
        </section>

        {analysis.candidates.length > 0 && <div className="public-next-cta">
          <div><strong>下一步：用授权周报验证候选问题</strong><p>补齐订单、净 GMV、补贴和各工具 ROI，才能判断钱漏在哪。</p></div>
          <button type="button" className="primary-action" onClick={() => document.getElementById('weekly-upload')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>导入周报</button>
        </div>}
      </section>}
    </>
  )
}
