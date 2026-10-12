export type SessionState = {
  accessToken: string | null
  organizationId: string | null
  branchId: string | null
  preview: boolean
}

const ORG_KEY = 'zaylan.organizationId'
const BRANCH_KEY = 'zaylan.branchId'
const PREVIEW_KEY = 'zaylan.preview'

function readStored(): SessionState {
  const preview = sessionStorage.getItem(PREVIEW_KEY) === '1'
  return {
    accessToken: null,
    organizationId: sessionStorage.getItem(ORG_KEY),
    branchId: sessionStorage.getItem(BRANCH_KEY),
    preview,
  }
}

let state: SessionState = readStored()
const listeners = new Set<() => void>()

function emit() {
  listeners.forEach((listener) => listener())
}

function persist(next: SessionState) {
  if (next.organizationId) sessionStorage.setItem(ORG_KEY, next.organizationId)
  else sessionStorage.removeItem(ORG_KEY)
  if (next.branchId) sessionStorage.setItem(BRANCH_KEY, next.branchId)
  else sessionStorage.removeItem(BRANCH_KEY)
  if (next.preview) sessionStorage.setItem(PREVIEW_KEY, '1')
  else sessionStorage.removeItem(PREVIEW_KEY)
}

export const sessionStore = {
  get: () => state,
  subscribe: (listener: () => void) => {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
  set(patch: Partial<SessionState>) {
    state = { ...state, ...patch }
    persist(state)
    emit()
  },
  clear() {
    state = { accessToken: null, organizationId: null, branchId: null, preview: false }
    persist(state)
    emit()
  },
}
