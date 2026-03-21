import type { UserReasoningProfile } from '../types/models'

interface ProfileCardProps {
  profile: UserReasoningProfile
}

export function ProfileCard({ profile }: ProfileCardProps) {
  return (
    <section className="card profile-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Adaptive layer</p>
          <h2>Your reasoning profile</h2>
          <p className="supporting-copy">A quick read on your deliberation habits, blind spots, and the themes you return to.</p>
        </div>
      </div>

      <div className="metric-grid">
        <article className="mini-card">
          <span className="metric-value">{profile.sessions_count}</span>
          <p>seeded prior sessions</p>
        </article>
        <article className="mini-card">
          <span className="metric-value">{Math.round(profile.override_frequency * 100)}%</span>
          <p>panel override rate</p>
        </article>
        <article className="mini-card">
          <span className="metric-value">{profile.avg_rounds_before_ending.toFixed(1)}</span>
          <p>average rounds</p>
        </article>
      </div>

      <div className="brief-grid">
        <section className="profile-group">
          <h3>Most engaged tags</h3>
          <div className="tag-row">
            {profile.most_engaged_tags.map((tag) => (
              <span className="tag" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        </section>

        <section className="profile-group">
          <h3>Blind spots to amplify</h3>
          <div className="tag-row">
            {profile.least_engaged_tags.map((tag) => (
              <span className="tag emphasis" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        </section>
      </div>

      <div className="profile-group">
        <h3>Ignored perspective types</h3>
        <ul className="brief-list">
          {profile.ignored_perspective_types.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </section>
  )
}
