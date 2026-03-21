import type { Persona, PersonaStance } from '../types/models'

interface PersonaCardProps {
  persona: Persona
  selected?: boolean
  onToggle?: (personaId: string) => void
  reasons?: string[]
  stance?: PersonaStance
  compact?: boolean
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

export function PersonaCard({
  persona,
  selected = false,
  onToggle,
  reasons,
  stance,
  compact = false,
}: PersonaCardProps) {
  return (
    <article className={`persona-card ${selected ? 'selected' : ''} ${compact ? 'compact' : ''}`}>
      <header className="persona-topline">
        <div className="persona-nameplate">
          <span className="persona-avatar" aria-hidden="true">
            {persona.avatar_emoji}
          </span>
          <div>
            <p className="eyebrow">{persona.visibility}</p>
            <h3>{persona.name}</h3>
          </div>
        </div>
        {onToggle ? (
          <button className="ghost-button" type="button" onClick={() => onToggle(persona.id)}>
            {selected ? 'Remove' : 'Add'}
          </button>
        ) : null}
      </header>

      <p className="persona-summary">{persona.summary}</p>

      <div className="persona-status-strip">
        {stance ? (
          <div className="stance-chip-row">
            <span className={`stance-pill stance-${stance.label}`}>{stance.label}</span>
            <span className="metric-pill">confidence {formatPercent(stance.confidence)}</span>
          </div>
        ) : null}

        <div className="tag-row">
          {persona.tags.map((tag) => (
            <span key={tag} className="tag">
              {tag}
            </span>
          ))}
        </div>
      </div>

      {stance ? <p className="supporting-copy persona-rationale">{stance.rationale}</p> : null}

      {reasons?.length ? (
        <ul className="reason-list">
          {reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}

      {!compact ? (
        <details className="persona-details">
          <summary>Inspect persona sheet</summary>
          <div className="persona-sheet">
            <p>
              <strong>Identity</strong>
              {persona.identity_anchor}
            </p>
            <p>
              <strong>Epistemic style</strong>
              {persona.epistemic_style}
            </p>
            <p>
              <strong>Voice</strong>
              {persona.argumentative_voice}
            </p>
            <div className="bias-stack">
              {persona.cognitive_biases.map((bias) => (
                <div key={`${persona.id}-${bias.type}`} className="bias-card">
                  <span className="bias-strength">{bias.strength}</span>
                  <strong>{bias.type}</strong>
                  <p>{bias.description}</p>
                </div>
              ))}
            </div>
          </div>
        </details>
      ) : null}
    </article>
  )
}
