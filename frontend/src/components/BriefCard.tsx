import type { DecisionBrief } from '../types/models'

interface BriefCardProps {
  brief: DecisionBrief
}

export function BriefCard({ brief }: BriefCardProps) {
  return (
    <section className="card brief-card brief-layout">
      <div className="section-heading brief-intro">
        <div>
          <p className="eyebrow">Decision brief</p>
          <h2>Where the panel landed</h2>
        </div>
      </div>
      <p className="brief-headline">{brief.headline}</p>
      <p className="supporting-copy">{brief.landscape_summary}</p>

      <div className="brief-grid brief-columns">
        <section className="brief-column">
          <h3>Strongest arguments</h3>
          <div className="stack">
            {brief.strongest_arguments.map((argument, index) => (
              <article key={`${argument.persona_name}-${argument.title}-${index}`} className="mini-card brief-argument">
                <p className="eyebrow">{argument.persona_name}</p>
                <strong>{argument.title}</strong>
                <p>{argument.explanation}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="brief-column">
          <h3>Key uncertainties</h3>
          <ul className="brief-list">
            {brief.key_uncertainties.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <h3>Blind spots</h3>
          <ul className="brief-list">
            {brief.blind_spots.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>

      <section>
        <h3>Suggested next steps</h3>
        <ol className="brief-list ordered">
          {brief.suggested_next_steps.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
      </section>
    </section>
  )
}
