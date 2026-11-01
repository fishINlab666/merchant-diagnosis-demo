import type { BusinessHealthResult, CityStrategy, PeerSample } from '../domain/businessHealth'
import { eligiblePeers } from '../domain/businessHealth'
import type { MerchantPerspective } from '../domain/merchantPerspective'
import type { WeeklyReport } from '../domain/types'
import { MerchantDecisionPanel } from './MerchantDecisionPanel'

const strategyNames: Record<CityStrategy, string> = {
  scale: '优先加码',
  'fix-funnel': '先修转化',
  'fix-profit': '先修毛利',
  'fix-basics': '先修基建',
}

const cityActions: Record<CityStrategy, string> = {
  scale: '保持基本盘并测试增量',
  'fix-funnel': '先修门店承接与转化',
  'fix-profit': '先修补贴、客单和毛利',
  'fix-basics': '先修基建并停止无效投入',
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

interface BusinessHealthViewProps {
  report: WeeklyReport
  analysis: BusinessHealthResult
  peers: PeerSample[]
  perspective: MerchantPerspective
}

export function BusinessHealthView({ report, analysis, peers, perspective }: BusinessHealthViewProps) {
  const eligible = eligiblePeers(report, peers)
  const excluded = peers.filter((peer) => !eligible.includes(peer))
  return (
    <article className="business-health merchant-health" aria-label={perspective.pageTitle}>
      <header className="health-header">
        <div>
          <p className="eyebrow">MERCHANT HEALTH · {perspective.report.synthetic ? '合成示例' : '商家授权数据'}</p>
          <h1>{perspective.pageTitle}</h1>
          <p className="report-subtitle">{perspective.report.store.alias} · {analysis.scope}</p>
        </div>
        <div className="health-position">
          <span>本店位置 · 经营事实</span>
          <strong>{analysis.headline}</strong>
        </div>
      </header>

      <MerchantDecisionPanel perspective={perspective} context="health" />

      <section className="health-section">
        <div className="section-heading">
          <div><h2>六维经营分析</h2><p>按门店、流量、投放、补贴、用户和分层下钻，缺数据就关闭对应模块。</p></div>
        </div>
        <div className="dimension-grid">
          {perspective.dimensions.map((item, index) => (
            <div className={`dimension ${item.status}`} data-dimension-id={item.id} key={item.id}>
              <div className="dimension-top"><h3 data-rank={`0${index + 1}`}>{item.title}</h3><span>{item.status === 'missing' ? '未提供' : item.status === 'risk' ? '风险' : item.status === 'watch' ? '关注' : '良好'}</span></div>
              <div className="dimension-facts">
                <strong>{item.merchant}</strong>
                <p>{item.comparison}</p>
                <small>{item.evidence}</small>
              </div>
              <div className="dimension-lens">{item.decisionInsight}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="health-section">
        <div className="section-heading">
          <div><h2>竞店样本｜找经营差距</h2><p>同平台、同商圈、同品类、同价格带、同周期；不是行业均值。</p></div>
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
          <div><h2>城市分层｜决定投入与退出</h2><p>UE 与增速同时看；合成样本只用于展示分层方法，不代表真实城市排名。</p></div>
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
              <p className="city-action">{cityActions[city.strategy]}</p>
              <small>合成城市样本，仅用于展示分层方法。</small>
            </div>
          ))}
        </div>
      </section>

      <section className="health-section role-next-actions">
        <div className="section-heading">
          <div><h2>下周经营动作</h2><p>每项都有负责人、复核指标、目标和停止条件。</p></div>
        </div>
        <div className="role-action-list">
          {perspective.followUps.map((item, index) => (
            <div className="role-action" key={item.action}>
              <span>0{index + 1}</span>
              <div><strong>{item.action}</strong><p>{item.owner} · {item.metric}</p><small>{item.target}；停止：{item.stopCondition}</small></div>
              <time>{item.reviewDate}</time>
            </div>
          ))}
        </div>
      </section>
    </article>
  )
}
