import type { MerchantPerspective } from '../domain/merchantPerspective'

interface MerchantDecisionPanelProps {
  perspective: MerchantPerspective
  context: 'health' | 'budget'
}

export function MerchantDecisionPanel({ perspective, context }: MerchantDecisionPanelProps) {
  const role = perspective.role ?? 'merchant'
  const roleLabel = role === 'ka' ? 'PLATFORM KA · 平台预算决策' : role === 'cs' ? 'CUSTOMER SUCCESS · 客户健康决策' : 'MERCHANT DECISION · 商家经营决策'
  return (
    <section className={`role-decision-panel merchant-decision-panel role-context-${context}`} data-decision-module={perspective.module.id} data-role={role} aria-label={perspective.module.title}>
      <div className="role-decision-heading">
        <div>
          <p className="eyebrow">{roleLabel}</p>
          <h2>{perspective.decisionQuestion}</h2>
          <p>{perspective.decisionSummary}</p>
        </div>
        <span>{perspective.module.title}</span>
      </div>
      <div className="role-decision-metrics">
        {perspective.metrics.map((metric) => (
          <div className="role-decision-metric" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </div>
        ))}
      </div>
      <div className="role-module-body">
        <div className="role-module-title"><h3>{perspective.module.title}</h3><p>{perspective.module.description}</p></div>
        <div className="role-module-grid">
          {perspective.module.cards.map((card, index) => (
            <div className="role-module-card" key={card.label}>
              <span>0{index + 1} · {card.label}</span>
              <strong>{card.value}</strong>
              <p>{card.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
