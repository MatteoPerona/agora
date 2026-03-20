import { createContext } from 'react'
import type { FlowDraft } from '../types/models'

export const EMPTY_DRAFT: FlowDraft = {
  prompt: '',
  documents: [],
  selectedPersonaIds: [],
  recommendation: null,
  recommendationSeedKey: null,
  activeSessionId: null,
}

export interface FlowDraftContextValue {
  draft: FlowDraft
  updateDraft: (patch: Partial<FlowDraft> | ((current: FlowDraft) => Partial<FlowDraft>)) => void
  resetDraft: () => void
}

export const FlowDraftContext = createContext<FlowDraftContextValue | null>(null)
