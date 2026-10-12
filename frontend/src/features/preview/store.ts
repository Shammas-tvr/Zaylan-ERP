import type { BranchInput, Organization, OrgStatus } from '../../shared/api/types.ts'
import { sessionStore } from '../../shared/session.ts'
import { initialPreview, type PreviewData } from './data.ts'

let data: PreviewData = structuredClone(initialPreview)

export function isPreview() {
  return sessionStore.get().preview
}

export function resetPreview() {
  data = structuredClone(initialPreview)
}

export function readPreview() {
  return data
}

function orgId() {
  const id = sessionStore.get().organizationId
  if (!id) throw new Error('Choose an organization first.')
  return id
}

function change(recipe: (draft: PreviewData) => void) {
  const draft = structuredClone(data)
  recipe(draft)
  data = draft
}

function remember(draft: PreviewData, org: string, action: string, summary: string) {
  draft.audit[org].unshift({
    id: crypto.randomUUID(),
    created_at: new Date().toISOString(),
    action,
    actor_name: draft.me.full_name,
    summary,
  })
}

export function previewCreateBranch(input: BranchInput) {
  const current = orgId()
  const branch = {
    id: crypto.randomUUID(),
    code: input.code.toUpperCase(),
    name: input.name,
    status: 'active' as const,
    timezone: input.timezone,
    phone: input.phone,
    email: input.email,
    address: input.address,
  }
  change((draft) => {
    draft.contexts[current].branches.unshift(branch)
    remember(draft, current, 'branch.created', `${branch.name} (${branch.code})`)
  })
  return branch
}

export function previewUpdateOrganization(patch: Partial<Organization>) {
  const current = orgId()
  change((draft) => {
    Object.assign(draft.contexts[current].organization, patch)
    const summary = draft.organizations.find((item) => item.id === current)
    if (summary && patch.name) summary.name = patch.name
    if (summary && patch.industry) summary.industry = patch.industry
    remember(draft, current, 'organization.updated', 'Organization profile saved')
  })
  return data.contexts[current].organization
}

export function previewUpdateBranding(patch: PreviewData['contexts'][string]['branding']) {
  const current = orgId()
  change((draft) => {
    draft.contexts[current].branding = patch
    const summary = draft.organizations.find((item) => item.id === current)
    if (summary) summary.branding = patch
    remember(draft, current, 'organization.branding_updated', 'Brand colors saved')
  })
  return patch
}

export function previewInvite(email: string, roleName: string) {
  const current = orgId()
  const invitation = {
    id: crypto.randomUUID(),
    email,
    role_name: roleName,
    status: 'pending' as const,
    expires_at: new Date(Date.now() + 72 * 60 * 60 * 1000).toISOString(),
  }
  change((draft) => {
    draft.invitations[current].unshift(invitation)
    remember(draft, current, 'member.invited', `${email} · ${roleName}`)
  })
  return invitation
}

export function previewRevokeInvitation(id: string) {
  const current = orgId()
  change((draft) => {
    const invitation = draft.invitations[current].find((item) => item.id === id)
    if (invitation) invitation.status = 'revoked'
    remember(draft, current, 'member.invitation_revoked', invitation?.email ?? id)
  })
}

export function previewSetTenantStatus(id: string, status: OrgStatus) {
  change((draft) => {
    const tenant = draft.tenants.find((item) => item.id === id)
    if (tenant) tenant.status = status
    const summary = draft.organizations.find((item) => item.id === id)
    if (summary) summary.status = status
    if (draft.contexts[id]) draft.contexts[id].organization.status = status
  })
}
