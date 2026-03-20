import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { BriefCard } from '../components/BriefCard'
import { DebateFeed } from '../components/DebateFeed'
import { SimulationGraph } from '../components/SimulationGraph'
import { TrajectoryChart } from '../components/TrajectoryChart'
import { api } from '../lib/api'
import type { DecisionBrief, SessionSnapshot } from '../types/models'

export function SimulationScreen() {
  const { sessionId = '' } = useParams()
  const [session, setSession] = useState<SessionSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [autoRun, setAutoRun] = useState(true)
  const [interjection, setInterjection] = useState('')
  const [error, setError] = useState('')
  const [inlineSummaryOpen, setInlineSummaryOpen] = useState(false)
  const [summaryOverlayOpen, setSummaryOverlayOpen] = useState(false)
  const advancingRef = useRef(false)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const snapshot = await api.getSession(sessionId)
        if (!cancelled) {
          setSession(snapshot)
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Could not load the simulation session.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    if (sessionId) {
      void load()
    }
    return () => {
      cancelled = true
    }
  }, [sessionId])

  async function advanceSession(sessionIdToAdvance: string) {
    if (advancingRef.current) {
      return
    }
    advancingRef.current = true
    try {
      const next = await api.advanceSession(sessionIdToAdvance)
      if (next.status === 'complete' && !next.brief) {
        const finished = await api.finishSession(sessionIdToAdvance)
        setSession(finished)
      } else {
        setSession(next)
      }
    } catch (advanceError) {
      setAutoRun(false)
      setError(advanceError instanceof Error ? advanceError.message : 'Could not advance the simulation.')
    } finally {
      advancingRef.current = false
    }
  }

  const advanceSessionOnce = useEffectEvent(async () => {
    if (!session || session.brief) {
      return
    }
    await advanceSession(session.session_id)
  })

  useEffect(() => {
    if (!autoRun || !session || session.status === 'complete' || session.brief) {
      return
    }

    const timer = window.setInterval(() => {
      void advanceSessionOnce()
    }, 1500)

    return () => {
      window.clearInterval(timer)
    }
  }, [autoRun, session])

  const lastPersonaMessage = [...(session?.messages ?? [])].reverse().find((message) => message.role === 'persona')

  async function handleSendInterjection() {
    if (!session || !interjection.trim()) {
      return
    }

    try {
      const updated = await api.addInterjection(session.session_id, interjection.trim())
      setSession(updated)
      setInterjection('')
    } catch (interjectionError) {
      setError(interjectionError instanceof Error ? interjectionError.message : 'Could not send the interjection.')
    }
  }

  async function handleFinishNow() {
    if (!session) {
      return
    }

    try {
      const finished = await api.finishSession(session.session_id)
      setSession(finished)
      setAutoRun(false)
    } catch (finishError) {
      setError(finishError instanceof Error ? finishError.message : 'Could not finish the simulation.')
    }
  }

  function downloadSummary(brief: DecisionBrief) {
    const markdown = buildBriefMarkdown(brief)
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'perspective-engine-summary.md'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  if (!sessionId) {
    return (
      <div className="screen-panel primary-panel">
        <h2>No session selected</h2>
        <p>Start from persona selection to create a simulation run.</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="screen-panel primary-panel">
        <h2>Loading simulation…</h2>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="screen-panel primary-panel">
        <h2>Session unavailable</h2>
        <p>{error || 'This run could not be restored from memory.'}</p>
        <Link className="secondary-button inline-link" to="/personas">
          Back to persona selection
        </Link>
      </div>
    )
  }

  return (
    <>
      <section className="simulation-header screen-panel">
        <div className="section-copy">
          <p className="eyebrow">Step 3</p>
          <h2>Run the simulation</h2>
          <p className="screen-summary">{session.decision}</p>
        </div>

        <div className="simulation-controls">
          <span className="metric-pill">round {session.current_round}/{session.round_goal}</span>
          <button className="secondary-button" type="button" onClick={() => setAutoRun((current) => !current)} disabled={session.status === 'complete'}>
            {autoRun ? 'Pause auto-run' : 'Resume auto-run'}
          </button>
          <button className="secondary-button" type="button" onClick={() => void advanceSession(session.session_id)} disabled={session.status === 'complete'}>
            Advance one round
          </button>
          <button className="ghost-button" type="button" onClick={() => void handleFinishNow()}>
            Finish now
          </button>
        </div>
      </section>

      {error ? <p className="inline-error">{error}</p> : null}

      <section className="simulation-layout">
        <article className="screen-panel graph-panel">
          <div className="section-row">
            <div>
              <p className="eyebrow">Interaction graph</p>
              <h3>Who is influencing whom</h3>
            </div>
            {lastPersonaMessage ? <span className="metric-pill">speaking: {lastPersonaMessage.author_name}</span> : null}
          </div>
          <SimulationGraph roster={session.roster} networkEdges={session.network_edges} messages={session.messages} />
        </article>

        <div className="simulation-sidebar">
          <article className="screen-panel chart-panel">
            <div className="section-row">
              <div>
                <p className="eyebrow">Opinion trajectories</p>
                <h3>How stances move over time</h3>
              </div>
            </div>
            <TrajectoryChart series={session.trajectories} roundGoal={session.round_goal} />
          </article>

          <article className="screen-panel transcript-panel">
            <div className="section-row">
              <div>
                <p className="eyebrow">Transcript</p>
                <h3>Interject when the room needs a push</h3>
              </div>
            </div>

            <textarea
              className="field textarea"
              rows={3}
              placeholder="Ask a question or introduce new information."
              value={interjection}
              onChange={(event) => setInterjection(event.target.value)}
            />
            <div className="button-row">
              <button className="primary-button" type="button" onClick={() => void handleSendInterjection()}>
                Send interjection
              </button>
              <Link className="secondary-button inline-link" to="/personas">
                Adjust panel
              </Link>
            </div>
            <DebateFeed messages={session.messages} />
          </article>
        </div>
      </section>

      {session.brief ? (
        <section className="screen-panel summary-dock">
          <div className="section-row spaced">
            <div>
              <p className="eyebrow">Summary</p>
              <h3>The simulation has finished</h3>
            </div>
            <div className="button-row">
              <button className="secondary-button" type="button" onClick={() => setInlineSummaryOpen((current) => !current)}>
                {inlineSummaryOpen ? 'Hide summary' : 'Show summary'}
              </button>
              <button className="secondary-button" type="button" onClick={() => setSummaryOverlayOpen(true)}>
                Expand summary
              </button>
              <button className="ghost-button" type="button" onClick={() => downloadSummary(session.brief!)}>
                Download .md
              </button>
            </div>
          </div>

          {inlineSummaryOpen ? <BriefCard brief={session.brief} /> : null}
        </section>
      ) : null}

      {summaryOverlayOpen && session.brief ? (
        <div className="summary-overlay" role="dialog" aria-modal="true">
          <div className="summary-overlay-panel">
            <div className="section-row spaced">
              <div>
                <p className="eyebrow">Expanded summary</p>
                <h3>Fullscreen decision brief</h3>
              </div>
              <div className="button-row">
                <button className="secondary-button" type="button" onClick={() => downloadSummary(session.brief!)}>
                  Download .md
                </button>
                <button className="ghost-button" type="button" onClick={() => setSummaryOverlayOpen(false)}>
                  Close
                </button>
              </div>
            </div>
            <BriefCard brief={session.brief} />
          </div>
        </div>
      ) : null}
    </>
  )
}

function buildBriefMarkdown(brief: DecisionBrief) {
  return [
    '# Perspective Engine Summary',
    '',
    `## Headline`,
    brief.headline,
    '',
    `## Landscape`,
    brief.landscape_summary,
    '',
    `## Strongest Arguments`,
    ...brief.strongest_arguments.flatMap((argument) => [`### ${argument.persona_name}: ${argument.title}`, argument.explanation, '']),
    `## Key Uncertainties`,
    ...brief.key_uncertainties.map((item) => `- ${item}`),
    '',
    `## Blind Spots`,
    ...brief.blind_spots.map((item) => `- ${item}`),
    '',
    `## Suggested Next Steps`,
    ...brief.suggested_next_steps.map((item, index) => `${index + 1}. ${item}`),
    '',
  ].join('\n')
}
