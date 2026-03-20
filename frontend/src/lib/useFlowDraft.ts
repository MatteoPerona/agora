import { useContext } from 'react'
import { FlowDraftContext } from './flowDraftContext'

export function useFlowDraft() {
  const context = useContext(FlowDraftContext)
  if (!context) {
    throw new Error('useFlowDraft must be used inside FlowDraftProvider.')
  }
  return context
}
