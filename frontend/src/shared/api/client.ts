import { api } from './axios'
import type {
  Branch,
  Invitation,
  Member,
  MembershipSummary,
  Organization,
  Paginated,
  Plan,
  PlatformMetrics,
  PlatformTenant,
  Role,
  Session,
  TenantContext,
  User,
} from './types'

export const authApi = {
  login: (email: string, password: string) =>
    api.post<Session>('/auth/login', { email, password }).then((r) => r.data),
  logout: () => api.post('/auth/logout').then(() => undefined),
  me: () => api.get<User>('/me/').then((r) => r.data),
  organizations: () => api.get<MembershipSummary[]>('/me/organizations').then((r) => r.data),
  context: () => api.get<TenantContext>('/me/context').then((r) => r.data),
  lookupInvitation: (token: string) =>
    api
      .post<{ organization_name: string; email: string; account_exists: boolean }>(
        '/auth/invitations/lookup',
        { token },
      )
      .then((r) => r.data),
  acceptInvitation: (payload: { token: string; full_name?: string; password?: string }) =>
    api.post<Session>('/auth/invitations/accept', payload).then((r) => r.data),
}

export const tenantApi = {
  organization: () => api.get<Organization>('/organization/').then((r) => r.data),
  updateOrganization: (data: Partial<Organization>) =>
    api.patch<Organization>('/organization/', data).then((r) => r.data),
  updateBranding: (data: Record<string, string>) =>
    api.patch('/organization/branding', data).then((r) => r.data),
  members: () => api.get<Paginated<Member>>('/organization/members').then((r) => r.data),
  roles: () => api.get<Role[]>('/organization/roles').then((r) => r.data),
  invitations: () =>
    api.get<Paginated<Invitation>>('/organization/invitations').then((r) => r.data),
  invite: (payload: {
    email: string
    assignments: { role_id: string; scope: string }[]
    branch_ids: string[]
  }) =>
    api
      .post<{ invitation: Invitation; invitation_url: string }>(
        '/organization/invitations',
        payload,
      )
      .then((r) => r.data),
  branches: () => api.get<Paginated<Branch>>('/branches/').then((r) => r.data),
  createBranch: (payload: { code: string; name: string }) =>
    api.post<Branch>('/branches/', payload).then((r) => r.data),
}

export const platformApi = {
  tenants: () => api.get<Paginated<PlatformTenant>>('/platform/tenants').then((r) => r.data),
  onboard: (payload: Record<string, string>) =>
    api
      .post<{ tenant: PlatformTenant; owner_invitation_url: string }>('/platform/tenants', payload)
      .then((r) => r.data),
  setStatus: (id: string, status: string, reason: string) =>
    api.post(`/platform/tenants/${id}/status`, { status, reason }).then((r) => r.data),
  plans: () => api.get<Plan[]>('/platform/plans').then((r) => r.data),
  metrics: () => api.get<PlatformMetrics>('/platform/metrics').then((r) => r.data),
}
