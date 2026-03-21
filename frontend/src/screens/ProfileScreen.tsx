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
          <h2>Reasoning profile</h2>
          <p className="screen-summary">
            A compact reference for how you tend to think, where you are strong, and which perspectives deserve more
            pressure before a decision is finalized.
          </p>
        </div>

        {error ? <p className="inline-error">{error}</p> : null}
        {profile ? (
          <div className="stack">
            <article className="mini-card">
              <p className="eyebrow">Reference note</p>
              <p className="supporting-copy">
                Use this view to calibrate panel selection and to spot the defaults you may be overusing in a debate.
              </p>
            </article>
            <ProfileCard profile={profile} />
          </div>
        ) : (
          <p className="supporting-copy">Loading profile…</p>
        )}
      </article>
    </section>
  )
}
