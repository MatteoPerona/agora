import { startTransition, useDeferredValue, useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { PersonaCard } from '../components/PersonaCard'
import { api } from '../lib/api'
import { useFlowDraft } from '../lib/useFlowDraft'
import type { Persona, UserReasoningProfile } from '../types/models'

export function PersonasScreen() {
  const navigate = useNavigate()
  const { draft, updateDraft } = useFlowDraft()
  const [personas, setPersonas] = useState<Persona[]>([])
  const [profile, setProfile] = useState<UserReasoningProfile | null>(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [recommending, setRecommending] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState('')

  const deferredSearch = useDeferredValue(search)
  const selectionSeed = `${draft.prompt}::${draft.documents.map((document) => document.id).join(',')}`

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [personaResponse, profileResponse] = await Promise.all([api.listPersonas(), api.getProfile()])
        if (!cancelled) {
          setPersonas(personaResponse)
          setProfile(profileResponse)
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Could not load the persona library.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!draft.prompt.trim() || !personas.length || !profile) {
      return
    }
    if (draft.recommendation && draft.recommendationSeedKey === selectionSeed) {
      return
    }

    let cancelled = false

    async function fetchRecommendations() {
      try {
        setRecommending(true)
        const response = await api.recommendPanel({
          decision: draft.prompt,
          document_ids: draft.documents.map((document) => document.id),
          panel_size: 5,
          manual_ids: [],
        })
        if (!cancelled) {
          updateDraft({
            recommendation: response,
            selectedPersonaIds: response.suggested_ids,
            recommendationSeedKey: selectionSeed,
          })
        }
      } catch (recommendationError) {
        if (!cancelled) {
          setError(recommendationError instanceof Error ? recommendationError.message : 'Could not preselect personas.')
        }
      } finally {
        if (!cancelled) {
          setRecommending(false)
        }
      }
    }

    void fetchRecommendations()
    return () => {
      cancelled = true
    }
  }, [draft.documents, draft.prompt, draft.recommendation, draft.recommendationSeedKey, personas.length, profile, selectionSeed, updateDraft])

  if (!draft.prompt.trim()) {
    return <Navigate to="/start" replace />
  }

  const visiblePersonas = personas.filter((persona) =>
    `${persona.name} ${persona.summary} ${persona.tags.join(' ')}`.toLowerCase().includes(deferredSearch.toLowerCase()),
  )
  const selectedPersonas = personas.filter((persona) => draft.selectedPersonaIds.includes(persona.id))

  function togglePersona(personaId: string) {
    updateDraft((current) => ({
      selectedPersonaIds: current.selectedPersonaIds.includes(personaId)
        ? current.selectedPersonaIds.filter((id) => id !== personaId)
        : current.selectedPersonaIds.length >= 8
          ? current.selectedPersonaIds
          : [...current.selectedPersonaIds, personaId],
    }))
  }

  async function handleStartSimulation() {
    if (draft.selectedPersonaIds.length < 3) {
      setError('Select at least 3 personas before starting the simulation.')
      return
    }

    try {
      setStarting(true)
      const session = await api.createSession({
        decision: draft.prompt,
        document_ids: draft.documents.map((document) => document.id),
        persona_ids: draft.selectedPersonaIds,
        round_goal: 6,
      })
      updateDraft({ activeSessionId: session.session_id })
      navigate(`/simulation/${session.session_id}`)
    } catch (sessionError) {
      setError(sessionError instanceof Error ? sessionError.message : 'Could not start the simulation.')
    } finally {
      setStarting(false)
    }
  }

  return (
    <section className="screen-grid personas-screen">
      <article className="screen-panel primary-panel">
        <div className="section-copy">
          <p className="eyebrow">Step 2</p>
          <h2>Choose the panel</h2>
          <p className="screen-summary">
            Start from the LLM’s preselected set, then search and swap personas until the room feels like the right
            mix of tension and expertise.
          </p>
        </div>

        <div className="context-strip">
          <div className="context-chip">
            <span className="eyebrow">Prompt</span>
            <p>{draft.prompt}</p>
          </div>
          {draft.documents.length ? (
            <div className="context-chip">
              <span className="eyebrow">Documents</span>
              <p>{draft.documents.map((document) => document.filename).join(', ')}</p>
            </div>
          ) : null}
        </div>

        {draft.recommendation?.selection_notice ? (
          <p className="inline-notice">{draft.recommendation.selection_notice}</p>
        ) : null}
        {error ? <p className="inline-error">{error}</p> : null}

        <div className="section-row">
          <div>
            <p className="eyebrow">Preselected personas</p>
            <h3>{recommending ? 'Building the opening panel…' : 'Suggested by the selector'}</h3>
          </div>
        </div>

        <div className="recommendation-strip">
          {draft.recommendation?.recommendations.map((entry) => (
            <PersonaCard
              key={entry.persona.id}
              persona={entry.persona}
              selected={draft.selectedPersonaIds.includes(entry.persona.id)}
              onToggle={togglePersona}
              reasons={entry.reasons}
              stance={entry.initial_stance}
              compact
            />
          ))}
        </div>

        <div className="section-row spaced">
          <div>
            <p className="eyebrow">Search library</p>
            <h3>All personas</h3>
          </div>
          <input
            className="field search-field"
            placeholder="Search by name, summary, or tags"
            value={search}
            onChange={(event) =>
              startTransition(() => {
                setSearch(event.target.value)
              })
            }
          />
        </div>

        {loading ? <p className="supporting-copy">Loading personas…</p> : null}

        <div className="persona-grid">
          {visiblePersonas.map((persona) => {
            const recommendation = draft.recommendation?.recommendations.find((entry) => entry.persona.id === persona.id)
            return (
              <PersonaCard
                key={persona.id}
                persona={persona}
                selected={draft.selectedPersonaIds.includes(persona.id)}
                onToggle={togglePersona}
                reasons={recommendation?.reasons}
                stance={recommendation?.initial_stance}
              />
            )
          })}
        </div>
      </article>

      <aside className="screen-panel supporting-panel sticky-panel">
        <div className="section-copy">
          <p className="eyebrow">Selected panel</p>
          <h3>{draft.selectedPersonaIds.length} personas ready</h3>
          <p className="supporting-copy">
            Keep at least three. The selected strip stays pinned so you can swap without losing track of the room.
          </p>
        </div>

        {profile ? (
          <div className="mini-card">
            <p className="eyebrow">Blind spot guidance</p>
            <p className="supporting-copy">{draft.recommendation?.blind_spot_message ?? profile.ignored_perspective_types.join(', ')}</p>
          </div>
        ) : null}

        <div className="selected-panel-stack">
          {selectedPersonas.map((persona) => {
            const recommendation = draft.recommendation?.recommendations.find((entry) => entry.persona.id === persona.id)
            return (
              <PersonaCard
                key={persona.id}
                persona={persona}
                selected
                onToggle={togglePersona}
                reasons={recommendation?.reasons}
                stance={recommendation?.initial_stance}
                compact
              />
            )
          })}
        </div>

        <div className="button-column">
          <button className="primary-button" type="button" onClick={() => void handleStartSimulation()} disabled={starting || draft.selectedPersonaIds.length < 3}>
            {starting ? 'Starting…' : 'Start simulation'}
          </button>
          <button className="secondary-button" type="button" onClick={() => navigate('/start')}>
            Back to prompt
          </button>
        </div>
      </aside>
    </section>
  )
}
