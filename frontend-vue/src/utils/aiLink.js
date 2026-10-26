export const AI_CONTEXT_EVENT = 'ai-context-request'

export function emitAiContext(detail) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(AI_CONTEXT_EVENT, { detail }))
}