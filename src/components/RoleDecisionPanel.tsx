import type { RolePerspective } from '../domain/rolePerspective'

interface RoleDecisionPanelProps {
  perspective: RolePerspective
  context: 'health' | 'budget'
}

export function RoleDecisionPanel({ perspective, context }: RoleDecisionPanelProps) {
  return (
    <section
      className={`role-decision-panel role-${perspective.role} role-context-${context}`}
      data-decision-module={perspective.module.id}
      aria-label={perspective.module.title}
    >
      <div className="role-decision-heading">
        <div>
          <p className="eyebrow">ROLE DECISION · {perspective.role === 'ka' ? '平台 KA' : perspective.role === 'agency' ? '服务商' : 'SaaS 客户成功'}</p>
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
        <div className="role-module-title">
          <h3>{perspective.module.title}</h3>
          <p>{perspective.module.description}</p>
        </div>
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
