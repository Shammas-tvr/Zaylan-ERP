const ORG_KEY = "zaylan.activeOrganization"

let accessToken: string | null = null
let organizationId: string | null = sessionStorage.getItem(ORG_KEY)

export function getAccessToken() {
  return accessToken
}

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function getOrganizationId() {
  return organizationId
}

export function setOrganizationId(id: string | null) {
  organizationId = id
  if (id) sessionStorage.setItem(ORG_KEY, id)
  else sessionStorage.removeItem(ORG_KEY)
}

export function clearSession() {
  accessToken = null
  organizationId = null
  sessionStorage.removeItem(ORG_KEY)
}
