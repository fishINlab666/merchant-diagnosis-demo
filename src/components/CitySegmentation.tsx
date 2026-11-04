import type { CityAnalysis } from '../domain/businessHealth'
import { buildCitySegments, CITY_SEGMENT_ACTIONS, CITY_SEGMENT_LABELS, type CityQuadrant } from '../domain/citySegments'

const colors: Record<CityQuadrant, string> = {
  scale: '#34A853',
  hold: '#4285F4',
  adjust: '#FBBC04',
  fix: '#EA4335',
}

export function CitySegmentation({ cities, synthetic }: { cities: CityAnalysis[]; synthetic: boolean }) {
  const segments = buildCitySegments(cities)
  if (!segments.length) return (
    <section className="city-segmentation role-special-module">
      <div className="section-heading"><span className="section-number">03</span><div><h2>城市／门店分层</h2><p>缺少同口径增长与 UE 样本，不生成城市排名或资源承诺。</p></div></div>
      <p className="empty-evidence">请补充同平台、同品类、同价格带、同周期的城市或门店样本。</p>
    </section>
  )
  const growthValues = segments.map((item) => item.growth)
  const ueValues = segments.map((item) => item.ue)
  const xMin = Math.min(0, ...growthValues) - 0.02
  const xMax = Math.max(0.1, ...growthValues) + 0.02
  const yMin = Math.min(0, ...ueValues) - 0.02
  const yMax = Math.max(0.1, ...ueValues) + 0.02
  const x = (value: number) => 48 + (value - xMin) / (xMax - xMin) * 400
  const y = (value: number) => 220 - (value - yMin) / (yMax - yMin) * 180
  const counts = Object.fromEntries((['scale', 'hold', 'adjust', 'fix'] as CityQuadrant[]).map((key) => [key, segments.filter((item) => item.quadrant === key).length])) as Record<CityQuadrant, number>
  return (
    <section className="city-segmentation role-special-module" aria-labelledby="city-segmentation-title">
      <div className="section-heading">
        <span className="section-number">03</span>
        <div><h2 id="city-segmentation-title">城市分层：哪些加码、哪些先修</h2><p>{segments.length} 个{synthetic ? '合成' : '授权'}城市样本 · 增长 × UE；阈值用于资源讨论，不代表行业排名。</p></div>
      </div>
      <div className="city-segmentation-layout">
        <div className="city-quadrant-chart">
          <svg viewBox="0 0 500 260" role="img" aria-label="城市增长与 UE 四象限分层图">
            <rect x="48" y="40" width="400" height="180" fill="#F8FAFC" stroke="#E0E3E8" />
            <line x1={x(0.05)} x2={x(0.05)} y1="40" y2="220" stroke="#9AA0A6" strokeDasharray="4 4" />
            <line x1="48" x2="448" y1={y(0)} y2={y(0)} stroke="#9AA0A6" strokeDasharray="4 4" />
            <text x="55" y="55" className="quadrant-label hold">稳住 {counts.hold}</text>
            <text x="440" y="55" textAnchor="end" className="quadrant-label scale">加码 {counts.scale}</text>
            <text x="55" y="210" className="quadrant-label fix">收缩整改 {counts.fix}</text>
            <text x="440" y="210" textAnchor="end" className="quadrant-label adjust">调结构 {counts.adjust}</text>
            {segments.map((segment) => <g key={segment.city}>
              <circle cx={x(segment.growth)} cy={y(segment.ue)} r="7" fill={colors[segment.quadrant]} />
              <text x={x(segment.growth) + 10} y={y(segment.ue) + 4} className="city-point-label">{segment.city}</text>
            </g>)}
            <text x="248" y="250" textAnchor="middle" className="chart-axis-label">增长率（分界 5%）→</text>
            <text x="16" y="130" textAnchor="middle" className="chart-axis-label" transform="rotate(-90 16 130)">单店 UE →</text>
          </svg>
        </div>
        <div className="city-segment-table-wrap">
          <table className="city-segment-table">
            <thead><tr><th>分层</th><th>城市</th><th>资源动作</th></tr></thead>
            <tbody>{(['scale', 'hold', 'adjust', 'fix'] as CityQuadrant[]).map((key) => <tr key={key}>
              <td><span className={`segment-badge ${key}`}>{CITY_SEGMENT_LABELS[key]} {counts[key]}</span></td>
              <td>{segments.filter((item) => item.quadrant === key).map((item) => item.city).join('、') || '—'}</td>
              <td>{CITY_SEGMENT_ACTIONS[key]}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
