import type { BusinessHealthResult, CityStrategy, PeerSample } from '../domain/businessHealth'
import { eligiblePeers } from '../domain/businessHealth'
import type { Role, WeeklyReport } from '../domain/types'

const strategyNames: Record<CityStrategy, string> = {
  scale: '优先加码',
  'fix-funnel': '先修转化',
  'fix-profit': '先修毛利',
  'fix-basics': '先修基建',
}

const roleGuidance: Record<Role, string> = {
  ka: '把商圈和城市差异转成 JBP 与预算分层',
  agency: '把六维诊断转成门店分层服务包',
  cs: '把经营健康度变化纳入续费风险复核',
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

interface BusinessHealthViewProps {
  report: WeeklyReport
  analysis: BusinessHealthResult
  peers: PeerSample[]
  role: Role
}

export function BusinessHealthView({ report, analysis, peers, role }: BusinessHealthViewProps) {
  const eligible = eligiblePeers(report, peers)
  const excluded = peers.filter((peer) => !eligible.includes(peer))
  return (
    <article className="business-health" aria-label="商户经营全景">
      <header className="health-header">
        <div>
          <p className="eyebrow">MERCHANT HEALTH · 合成样本</p>
          <h1>经营全景</h1>
          <p className="report-subtitle">{analysis.scope}</p>
        </div>
        <div className="health-position">
          <span>本店位置</span>
          <strong>{analysis.headline}</strong>
        </div>
      </header>

      <div className="health-guidance">{roleGuidance[role]}</div>

      <section className="health-section">
        <div className="section-heading">
          <div><h2>六维经营分析</h2><p>从门店到用户，不只看投放工具。</p></div>
        </div>
        <div className="dimension-grid">
          {analysis.dimensions.map((item) => (
            <div className={`dimension ${item.status}`} key={item.id}>
              <div className="dimension-top"><h3>{item.title}</h3><span>{item.status === 'missing' ? '未提供' : item.status === 'risk' ? '风险' : item.status === 'watch' ? '关注' : '良好'}</span></div>
              <strong>{item.merchant}</strong>
              <p>{item.comparison}</p>
              <small>{item.evidence}</small>
            </div>
          ))}
        </div>
      </section>

      <section className="health-section">
        <div className="section-heading">
          <div><h2>竞店样本</h2><p>同平台、同商圈、同品类、同价格带、同周期；不是行业均值。</p></div>
        </div>
        <p className="sample-summary">{analysis.sampleSize} 家合格样本{analysis.peerMedian && ` · 净 GMV 中位数 ${analysis.peerMedian.netGmv.toLocaleString('zh-CN')} 元 · 评分中位数 ${analysis.peerMedian.rating}`}</p>
        {analysis.peerMedian && <p className="sample-median">P1 {percent(analysis.peerMedian.p1)} · P2 {percent(analysis.peerMedian.p2)} · 补贴率 {percent(analysis.peerMedian.subsidyRate)} · 复购 {percent(analysis.peerMedian.repeatCustomerRate)} · 会员 {percent(analysis.peerMedian.memberShare)}</p>}
        <div className="table-scroll">
          <table className="peer-table">
            <thead><tr><th>商户</th><th>评分</th><th>P1／P2</th><th>净 GMV</th><th>补贴率</th><th>复购／会员</th></tr></thead>
            <tbody>{eligible.map((peer) => <tr key={peer.peerId}>
              <td data-label="商户">{peer.alias}</td><td data-label="评分">{peer.rating}</td><td data-label="P1／P2">{percent(peer.p1)}／{percent(peer.p2)}</td><td data-label="净 GMV">{peer.netGmv.toLocaleString('zh-CN')} 元</td><td data-label="补贴率">{percent(peer.subsidyRate)}</td><td data-label="复购／会员">{percent(peer.repeatCustomerRate)}／{percent(peer.memberShare)}</td>
            </tr>)}</tbody>
          </table>
        </div>
        {excluded.length > 0 && <div className="excluded-peers">
          <strong>剔除样本</strong>
          {excluded.map((peer) => <p key={peer.peerId}>{peer.alias}：城市／商圈不一致，不纳入本店对比。</p>)}
        </div>}
      </section>

      <section className="health-section">
        <div className="section-heading">
          <div><h2>城市分层</h2><p>按 UE 与增速决定加码、提效、修毛利或修基建。</p></div>
        </div>
        <div className="city-grid">
          {analysis.cities.map((city) => (
            <div className={`city-card ${city.strategy}`} key={city.city}>
              <div className="city-heading"><h3>{city.city}</h3><span>{strategyNames[city.strategy]}</span></div>
              <dl>
                <div><dt>UE</dt><dd>{city.ue.toFixed(2)}</dd></div>
                <div><dt>增速</dt><dd>{percent(city.growth)}</dd></div>
                <div><dt>净 GMV 中位数</dt><dd>{city.netGmvMedian.toLocaleString('zh-CN')} 元</dd></div>
                <div><dt>P2／ROI 中位数</dt><dd>{percent(city.p2Median)}／{city.roiMedian}</dd></div>
                <div><dt>补贴率中位数</dt><dd>{percent(city.subsidyRateMedian)}</dd></div>
              </dl>
              <small>合成城市样本，仅用于展示分层方法。</small>
            </div>
          ))}
        </div>
      </section>
    </article>
  )
}
