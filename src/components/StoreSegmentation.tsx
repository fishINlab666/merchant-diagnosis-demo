import { CITY_SEGMENT_ACTIONS, CITY_SEGMENT_LABELS, type CityQuadrant } from '../domain/citySegments'
import { buildStoreSegments, type StoreSegmentSample } from '../domain/storeSegments'

const colors: Record<CityQuadrant, string> = { scale: '#34A853', hold: '#4285F4', adjust: '#FBBC04', fix: '#EA4335' }
const quadrants: CityQuadrant[] = ['scale', 'hold', 'adjust', 'fix']

export function StoreSegmentation({ stores, synthetic }: { stores: StoreSegmentSample[]; synthetic: boolean }) {
  const segments = buildStoreSegments(stores)
  if (!segments.length) return (
    <section className="store-segmentation role-special-module">
      <div className="section-heading"><span className="section-number">03</span><div><h2>门店分层：哪些店加码、哪些店先修</h2><p>缺少同口径增长与 UE 样本，不生成门店排名或资源承诺。</p></div></div>
      <p className="empty-evidence">请补充同平台、同品类、同价格带、同周期的门店增长与 UE 数据。</p>
    </section>
  )
  const growthValues = segments.map((store) => store.growth)
  const ueValues = segments.map((store) => store.ue)
  const xMin = Math.min(-0.02, ...growthValues) - 0.01
  const xMax = Math.max(0.1, ...growthValues) + 0.01
  const yMin = Math.min(-0.02, ...ueValues) - 0.01
  const yMax = Math.max(0.02, ...ueValues) + 0.01
  const x = (value: number) => 48 + (value - xMin) / (xMax - xMin) * 400
  const y = (value: number) => 220 - (value - yMin) / (yMax - yMin) * 180
  const counts = Object.fromEntries(quadrants.map((key) => [key, segments.filter((store) => store.quadrant === key).length])) as Record<CityQuadrant, number>
  return (
    <section className="store-segmentation role-special-module" aria-labelledby="store-segmentation-title">
      <div className="section-heading">
        <span className="section-number">03</span>
        <div><h2 id="store-segmentation-title">门店分层：哪些店加码、哪些店先修</h2><p>{segments.length} 家{synthetic ? '合成' : '授权'}门店 · {new Set(segments.map((store) => store.city)).size} 城 · 增长 × UE；每个点都是一家门店。</p></div>
      </div>
      <div className="store-segmentation-layout">
        <div className="store-quadrant-chart">
          <svg viewBox="0 0 500 260" role="img" aria-label={`${segments.length} 家门店增长与 UE 散点分层图`}>
            <rect x="48" y="40" width="400" height="180" fill="#F8FAFC" stroke="#E0E3E8" />
            <line x1={x(0.05)} x2={x(0.05)} y1="40" y2="220" stroke="#9AA0A6" strokeDasharray="4 4" />
            <line x1="48" x2="448" y1={y(0)} y2={y(0)} stroke="#9AA0A6" strokeDasharray="4 4" />
            <text x="55" y="55" className="quadrant-label hold">稳住 {counts.hold}</text>
            <text x="440" y="55" textAnchor="end" className="quadrant-label scale">加码 {counts.scale}</text>
            <text x="55" y="210" className="quadrant-label fix">收缩整改 {counts.fix}</text>
            <text x="440" y="210" textAnchor="end" className="quadrant-label adjust">调结构 {counts.adjust}</text>
            {segments.map((store) => <circle className="store-point" key={store.storeId} cx={x(store.growth)} cy={y(store.ue)} r="3.6" fill={colors[store.quadrant]} opacity="0.78" data-quadrant={store.quadrant}>
              <title>{store.alias} · {store.city} · 增长 {(store.growth * 100).toFixed(1)}% · UE {store.ue.toFixed(2)}</title>
            </circle>)}
            <text x="248" y="250" textAnchor="middle" className="chart-axis-label">门店增长率（分界 5%）→</text>
            <text x="16" y="130" textAnchor="middle" className="chart-axis-label" transform="rotate(-90 16 130)">单店 UE →</text>
          </svg>
        </div>
        <div className="store-segment-table-wrap">
          <table className="store-segment-table">
            <thead><tr><th>分层</th><th>门店数</th><th>动作</th></tr></thead>
            <tbody>{quadrants.map((key) => <tr key={key}>
              <td><span className={`segment-badge ${key}`}>{CITY_SEGMENT_LABELS[key]}</span></td>
              <td>{counts[key]}</td>
              <td>{CITY_SEGMENT_ACTIONS[key]}</td>
            </tr>)}</tbody>
          </table>
          <p className="chart-caption">分层数量由门店数据实时计算；合成样本只用于展示方法，不代表真实门店排名。</p>
        </div>
      </div>
    </section>
  )
}
