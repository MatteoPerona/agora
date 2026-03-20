import { useEffect, useState, type ReactNode } from 'react'
import type { FlowDraft } from '../types/models'
import { EMPTY_DRAFT, FlowDraftContext } from './flowDraftContext'

const STORAGE_KEY = 'perspective-engine-flow-draft'

function readInitialDraft(): FlowDraft {
  if (typeof window === 'undefined') {
    return EMPTY_DRAFT
  }

  const raw = window.sessionStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return EMPTY_DRAFT
  }

  try {
    return { ...EMPTY_DRAFT, ...JSON.parse(raw) }
  } catch {
    return EMPTY_DRAFT
  }
}

export function FlowDraftProvider({ children }: { children: ReactNode }) {
  const [draft, setDraft] = useState<FlowDraft>(readInitialDraft)

  useEffect(() => {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(draft))
  }, [draft])

  function updateDraft(patch: Partial<FlowDraft> | ((current: FlowDraft) => Partial<FlowDraft>)) {
    setDraft((current) => ({
      ...current,
      ...(typeof patch === 'function' ? patch(current) : patch),
    }))
  }

  function resetDraft() {
    setDraft(EMPTY_DRAFT)
  }

  return (
    <FlowDraftContext.Provider value={{ draft, updateDraft, resetDraft }}>
      {children}
    </FlowDraftContext.Provider>
  )
}
