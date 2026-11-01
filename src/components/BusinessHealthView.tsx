import type { BusinessHealthResult, CityStrategy, PeerSample } from '../domain/businessHealth'
import { eligiblePeers } from '../domain/businessHealth'
import type { RolePerspective } from '../domain/rolePerspective'
import type { FollowUp, WeeklyReport } from '../domain/types'
import { RoleDecisionPanel } from './RoleDecisionPanel'

const strategyNames: Record<CityStrategy, string> = {
  scale: '优先加码',
  'fix-funnel': '先修转化',
  'fix-profit': '先修毛利',
  'fix-basics': '先修基建',
}

const actionTitles = {
  ka: '下周 JBP 与预算动作',
  agency: '本周客户交付动作',
  cs: '本周客户干预动作',
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

interface BusinessHealthViewProps {
  report: WeeklyReport
  analysis: BusinessHealthResult
  peers: PeerSample[]
  perspective: RolePerspective
  followUps: FollowUp[]
}

export function BusinessHealthView({ report, analysis, peers, perspective, followUps }: BusinessHealthViewProps) {
  const eligible = eligiblePeers(report, peers)
  const excluded = peers.filter((peer) => !eligible.includes(peer))
  return (
    <article className={`business-health role-${perspective.role}`} aria-label={perspective.pageTitle}>
      <header className="health-header">
        <div>
          <p className="eyebrow">MERCHANT HEALTH · 合成样本</p>
          <h1>{perspective.pageTitle}</h1>
          <p className="report-subtitle">{analysis.scope}</p>
        </div>
        <div className="health-position">
          <span>本店位置 · 共用经营事实</span>
          <strong>{analysis.headline}</strong>
        </div>
      </header>

      <RoleDecisionPanel perspective={perspective} context="health" />

      <section className="health-section">
        <div className="section-heading">
          <div><h2>六维经营分析 · 角色优先级</h2><p>原始事实一致，分析顺序和决策含义随角色变化。</p></div>
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
              <div className="dimension-lens">{item.roleInsight}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="health-section">
        <div className="section-heading">
          <div><h2>{perspective.peerHeading}</h2><p>{perspective.peerDescription} 同平台、同商圈、同品类、同价格带、同周期；不是行业均值。</p></div>
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
          <div><h2>{perspective.cityHeading}</h2><p>{perspective.cityDescription}</p></div>
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
              <p className="city-action">{perspective.cityActions[city.strategy]}</p>
              <small>合成城市样本，仅用于展示分层方法。</small>
            </div>
          ))}
        </div>
      </section>

      <section className="health-section role-next-actions">
        <div className="section-heading">
          <div><h2>{actionTitles[perspective.role]}</h2><p>动作、负责人、复核指标和停止条件随角色决策变化。</p></div>
        </div>
        <div className="role-action-list">
          {followUps.map((item, index) => (
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
