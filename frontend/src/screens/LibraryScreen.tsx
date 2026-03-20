import { useDeferredValue, useEffect, useState } from 'react'
import { PersonaCard } from '../components/PersonaCard'
import { api } from '../lib/api'
import type { BiasConfig, CreatePersonaPayload, Persona } from '../types/models'

const DEFAULT_BIAS_NOTES = `confirmation bias: MODERATE - You trust evidence that matches your frame.
commitment bias: MODERATE - Once you have argued a position, reversing it feels costly.
availability bias: LOW - Vivid recent examples shape your intuition.`

const EMPTY_GUIDED_FORM: CreatePersonaPayload & { biasNotes: string } = {
  name: '',
  summary: '',
  identity_anchor: '',
  epistemic_style: '',
  argumentative_voice: '',
  tags: [],
  opinion_change_threshold: 'MODERATE',
  avatar_emoji: '🧭',
  visibility: 'private',
  creator_id: 'local-user',
  cognitive_biases: [],
  biasNotes: DEFAULT_BIAS_NOTES,
}

export function LibraryScreen() {
  const [personas, setPersonas] = useState<Persona[]>([])
  const [search, setSearch] = useState('')
  const [naturalLanguageDraft, setNaturalLanguageDraft] = useState(
    "A skeptical field operator who has seen ambitious product pivots fail because nobody priced the support burden honestly."
  )
  const [guidedDraft, setGuidedDraft] = useState(EMPTY_GUIDED_FORM)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const deferredSearch = useDeferredValue(search)

  useEffect(() => {
    void refreshPersonas()
  }, [])

  async function refreshPersonas() {
    try {
      const response = await api.listPersonas()
      setPersonas(response)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Could not load the library.')
    }
  }

  async function handleExpand() {
    try {
      setError('')
      const expanded = await api.expandPersona(naturalLanguageDraft)
      setGuidedDraft({
        ...expanded,
        biasNotes: expanded.cognitive_biases.map((bias) => `${bias.type}: ${bias.strength} - ${bias.description}`).join('\n'),
      })
      setNotice('Expanded the natural-language description into a structured persona draft.')
    } catch (expandError) {
      setError(expandError instanceof Error ? expandError.message : 'Could not expand the persona.')
    }
  }

  async function handleSave() {
    try {
      setSaving(true)
      setError('')
      const payload: CreatePersonaPayload = {
        ...guidedDraft,
        tags: guidedDraft.tags.filter(Boolean),
        cognitive_biases: parseBiasNotes(guidedDraft.biasNotes),
      }
      await api.createPersona(payload)
      setGuidedDraft(EMPTY_GUIDED_FORM)
      setNaturalLanguageDraft('')
      setNotice('Saved the new persona to the library.')
      await refreshPersonas()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not save the persona.')
    } finally {
      setSaving(false)
    }
  }

  const visiblePersonas = personas.filter((persona) =>
    `${persona.name} ${persona.summary} ${persona.tags.join(' ')}`.toLowerCase().includes(deferredSearch.toLowerCase()),
  )

  return (
    <section className="screen-grid library-screen">
      <article className="screen-panel primary-panel">
        <div className="section-copy">
          <p className="eyebrow">Library</p>
          <h2>Persona creation and management</h2>
          <p className="screen-summary">
            This is now outside the primary 3-step flow so the selection step can stay focused on choosing a panel.
          </p>
        </div>

        {notice ? <p className="inline-notice">{notice}</p> : null}
        {error ? <p className="inline-error">{error}</p> : null}

        <div className="builder-grid">
          <article className="screen-subpanel">
            <p className="eyebrow">Natural language</p>
            <textarea
              className="field textarea"
              rows={6}
              value={naturalLanguageDraft}
              onChange={(event) => setNaturalLanguageDraft(event.target.value)}
            />
            <button className="secondary-button" type="button" onClick={() => void handleExpand()}>
              Expand into persona sheet
            </button>
          </article>

          <article className="screen-subpanel">
            <p className="eyebrow">Guided builder</p>
            <div className="builder-fields">
              <input className="field" placeholder="Persona name" value={guidedDraft.name} onChange={(event) => setGuidedDraft((current) => ({ ...current, name: event.target.value }))} />
              <input className="field" placeholder="Summary" value={guidedDraft.summary} onChange={(event) => setGuidedDraft((current) => ({ ...current, summary: event.target.value }))} />
              <textarea className="field textarea" rows={3} placeholder="Identity anchor" value={guidedDraft.identity_anchor} onChange={(event) => setGuidedDraft((current) => ({ ...current, identity_anchor: event.target.value }))} />
              <textarea className="field textarea" rows={3} placeholder="Epistemic style" value={guidedDraft.epistemic_style} onChange={(event) => setGuidedDraft((current) => ({ ...current, epistemic_style: event.target.value }))} />
              <textarea className="field textarea" rows={3} placeholder="Argumentative voice" value={guidedDraft.argumentative_voice} onChange={(event) => setGuidedDraft((current) => ({ ...current, argumentative_voice: event.target.value }))} />
              <input
                className="field"
                placeholder="Tags, comma-separated"
                value={guidedDraft.tags.join(', ')}
                onChange={(event) =>
                  setGuidedDraft((current) => ({
                    ...current,
                    tags: event.target.value
                      .split(',')
                      .map((tag) => tag.trim())
                      .filter(Boolean),
                  }))
                }
              />
              <textarea className="field textarea codeish" rows={4} value={guidedDraft.biasNotes} onChange={(event) => setGuidedDraft((current) => ({ ...current, biasNotes: event.target.value }))} />
              <div className="inline-fields">
                <select className="field" value={guidedDraft.opinion_change_threshold} onChange={(event) => setGuidedDraft((current) => ({ ...current, opinion_change_threshold: event.target.value as CreatePersonaPayload['opinion_change_threshold'] }))}>
                  <option value="LOW">LOW threshold</option>
                  <option value="MODERATE">MODERATE threshold</option>
                  <option value="HIGH">HIGH threshold</option>
                </select>
                <input className="field" placeholder="Avatar emoji" value={guidedDraft.avatar_emoji} onChange={(event) => setGuidedDraft((current) => ({ ...current, avatar_emoji: event.target.value }))} />
                <select className="field" value={guidedDraft.visibility} onChange={(event) => setGuidedDraft((current) => ({ ...current, visibility: event.target.value as CreatePersonaPayload['visibility'] }))}>
                  <option value="private">Private</option>
                  <option value="public">Public</option>
                </select>
              </div>
              <button className="primary-button" type="button" onClick={() => void handleSave()} disabled={saving}>
                {saving ? 'Saving…' : 'Save persona'}
              </button>
            </div>
          </article>
        </div>
      </article>

      <aside className="screen-panel supporting-panel">
        <div className="section-row spaced">
          <div>
            <p className="eyebrow">Library search</p>
            <h3>{personas.length} personas</h3>
          </div>
          <input className="field search-field" placeholder="Search the library" value={search} onChange={(event) => setSearch(event.target.value)} />
        </div>
        <div className="selected-panel-stack">
          {visiblePersonas.map((persona) => (
            <PersonaCard key={persona.id} persona={persona} compact />
          ))}
        </div>
      </aside>
    </section>
  )
}

function parseBiasNotes(notes: string): BiasConfig[] {
  return notes
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^([^:]+):\s*(LOW|MODERATE|HIGH)\s*-\s*(.+)$/i)
      if (!match) {
        return null
      }
      return {
        type: match[1].trim(),
        strength: match[2].toUpperCase() as BiasConfig['strength'],
        description: match[3].trim(),
      }
    })
    .filter((value): value is BiasConfig => value !== null)
}

