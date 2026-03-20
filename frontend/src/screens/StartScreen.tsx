import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useFlowDraft } from '../lib/useFlowDraft'

interface PendingUpload {
  id: string
  file: File
  filename: string
  status: 'uploading' | 'failed'
  error?: string
}

export function StartScreen() {
  const navigate = useNavigate()
  const { draft, updateDraft } = useFlowDraft()
  const [prompt, setPrompt] = useState(draft.prompt)
  const [pendingUploads, setPendingUploads] = useState<PendingUpload[]>([])
  const [error, setError] = useState('')

  const uploading = pendingUploads.some((entry) => entry.status === 'uploading')

  async function uploadFile(file: File, pendingId: string) {
    try {
      const document = await api.uploadDocument(file)
      setPendingUploads((current) => current.filter((entry) => entry.id !== pendingId))
      updateDraft((current) => ({
        documents: [...current.documents, document],
        recommendation: null,
        recommendationSeedKey: null,
        selectedPersonaIds: [],
        activeSessionId: null,
      }))
    } catch (uploadError) {
      setPendingUploads((current) =>
        current.map((entry) =>
          entry.id === pendingId
            ? {
                ...entry,
                status: 'failed',
                error: uploadError instanceof Error ? uploadError.message : 'Upload failed.',
              }
            : entry,
        ),
      )
    }
  }

  async function handleFiles(files: FileList | null) {
    if (!files) {
      return
    }

    const nextEntries = Array.from(files).map((file) => ({
      id: crypto.randomUUID(),
      file,
      filename: file.name,
      status: 'uploading' as const,
    }))
    setPendingUploads((current) => [...current, ...nextEntries])

    for (const entry of nextEntries) {
      await uploadFile(entry.file, entry.id)
    }
  }

  async function handleRetry(entry: PendingUpload) {
    setPendingUploads((current) =>
      current.map((candidate) =>
        candidate.id === entry.id ? { ...candidate, status: 'uploading', error: undefined } : candidate,
      ),
    )
    await uploadFile(entry.file, entry.id)
  }

  async function handleRemoveDocument(documentId: string) {
    try {
      await api.deleteDocument(documentId)
    } catch {
      // Local draft state is the important part; backend cleanup is best effort.
    }

    updateDraft((current) => ({
      documents: current.documents.filter((document) => document.id !== documentId),
      recommendation: null,
      recommendationSeedKey: null,
      selectedPersonaIds: [],
      activeSessionId: null,
    }))
  }

  function handleContinue() {
    if (!prompt.trim()) {
      setError('Add the decision you want the panel to deliberate.')
      return
    }

    updateDraft({
      prompt: prompt.trim(),
      activeSessionId: null,
    })
    navigate('/personas')
  }

  return (
    <section className="screen-grid start-screen">
      <article className="screen-panel primary-panel">
        <div className="section-copy">
          <p className="eyebrow">Step 1</p>
          <h2>Frame the decision</h2>
          <p className="screen-summary">
            Give the engine the core question and any supporting material so the next screen can assemble a sharper
            panel around the real decision, not a vague summary.
          </p>
        </div>

        <label className="field-label" htmlFor="decision-prompt">
          Decision prompt
        </label>
        <textarea
          id="decision-prompt"
          className="field textarea hero-textarea"
          placeholder="Describe the decision, the stakes, and the constraints that matter."
          value={prompt}
          onChange={(event) => {
            setPrompt(event.target.value)
            setError('')
          }}
          rows={11}
        />

        <div className="button-row">
          <button className="primary-button" type="button" onClick={handleContinue} disabled={uploading}>
            Continue to persona selection
          </button>
          <label className="secondary-button upload-trigger">
            Upload documents
            <input
              type="file"
              accept=".txt,.md,.pdf"
              multiple
              hidden
              onChange={(event) => void handleFiles(event.target.files)}
            />
          </label>
        </div>

        {error ? <p className="inline-error">{error}</p> : null}
      </article>

      <aside className="screen-panel supporting-panel">
        <div className="section-copy">
          <p className="eyebrow">Document context</p>
          <h3>Related material</h3>
        </div>

        <p className="supporting-copy">Supported in this pass: `.txt`, `.md`, `.pdf`, up to 5 files and 10 MB each.</p>

        <div className="document-stack">
          {draft.documents.map((document) => (
            <article key={document.id} className="document-card">
              <div>
                <strong>{document.filename}</strong>
                <p>{document.extracted_text_preview}</p>
              </div>
              <button className="ghost-button" type="button" onClick={() => void handleRemoveDocument(document.id)}>
                Remove
              </button>
            </article>
          ))}

          {pendingUploads.map((entry) => (
            <article key={entry.id} className={`document-card ${entry.status === 'failed' ? 'failed' : ''}`}>
              <div>
                <strong>{entry.filename}</strong>
                <p>{entry.status === 'uploading' ? 'Uploading and extracting text…' : entry.error}</p>
              </div>
              {entry.status === 'failed' ? (
                <button className="ghost-button" type="button" onClick={() => void handleRetry(entry)}>
                  Retry
                </button>
              ) : null}
            </article>
          ))}

          {!draft.documents.length && !pendingUploads.length ? (
            <div className="empty-card">
              <h3>No documents yet</h3>
              <p>Attach investor notes, customer feedback, or any material that should influence persona selection.</p>
            </div>
          ) : null}
        </div>
      </aside>
    </section>
  )
}
