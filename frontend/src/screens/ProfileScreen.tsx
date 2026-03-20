import { useEffect, useState } from 'react'
import { ProfileCard } from '../components/ProfileCard'
import { api } from '../lib/api'
import type { UserReasoningProfile } from '../types/models'

export function ProfileScreen() {
  const [profile, setProfile] = useState<UserReasoningProfile | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const response = await api.getProfile()
        if (!cancelled) {
          setProfile(response)
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Could not load the reasoning profile.')
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="screen-grid profile-screen">
      <article className="screen-panel primary-panel">
        <div className="section-copy">
          <p className="eyebrow">Profile</p>
          <h2>Reasoning tendencies and blind spots</h2>
          <p className="screen-summary">
            The profile view now lives outside the primary flow so the main journey stays centered on the current
            decision, while this screen remains available as a reference and future tuning surface.
          </p>
        </div>

        {error ? <p className="inline-error">{error}</p> : null}
        {profile ? <ProfileCard profile={profile} /> : <p className="supporting-copy">Loading profile…</p>}
      </article>
    </section>
  )
}

