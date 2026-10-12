import type {
  AppNotification,
  AuditEvent,
  Branch,
  BranchInput,
  Branding,
  BrandOnboardInput,
  BrandOnboardResult,
  Expense,
  ExpenseCategory,
  ExpenseReportRow,
  ExpenseStatus,
  ExpenseSummary,
  Invitation,
  Me,
  Member,
  NotificationSettings,
  Organization,
  OrganizationSummary,
  OrgStatus,
  Page,
  PermissionGrant,
  Plan,
  PlatformMetrics,
  PlatformTenant,
  RecurringExpense,
  Role,
  SubscriptionSummary,
  WorkspaceContext,
} from './types.ts'
import { client } from './client.ts'
import { defaultBranding } from '../brand.ts'
import { sessionStore } from '../session.ts'
import {
  isPreview,
  previewCreateBranch,
  previewInvite,
  previewRevokeInvitation,
  previewSetTenantStatus,
  previewUpdateBranding,
  previewUpdateOrganization,
  readPreview,
  resetPreview,
} from '../../features/preview/store.ts'

function unwrap<T>(data: T[] | Page<T>) {
  return Array.isArray(data) ? data : data.results
}

function currentOrg() {
  const id = sessionStore.get().organizationId
  if (!id) throw new Error('Choose an organization first.')
  return id
}

function lower(value: string | undefined | null) {
  return (value ?? '').toLowerCase()
}

function mapBranding(raw: Partial<Branding> | null | undefined): Branding {
  return {
    ...defaultBranding,
    ...raw,
    display_name: raw?.display_name || defaultBranding.display_name,
  }
}

function mapOrganization(raw: Record<string, unknown>): Organization {
  return {
    id: String(raw.id),
    name: String(raw.name ?? ''),
    legal_name: String(raw.legal_name ?? ''),
    slug: String(raw.slug ?? ''),
    industry: lower(String(raw.industry)),
    status: lower(String(raw.status)) as OrgStatus,
    currency: String(raw.currency ?? 'INR'),
    timezone: String(raw.timezone ?? 'Asia/Kolkata'),
    locale: String(raw.locale ?? 'en-IN'),
    tax_registration_number: String(raw.tax_registration_number ?? ''),
    prices_include_tax: Boolean(raw.prices_include_tax),
    contact_email: String(raw.contact_email ?? ''),
    contact_phone: String(raw.contact_phone ?? ''),
    address: String(raw.address_line1 || raw.address || ''),
  }
}

function mapBranch(raw: Record<string, unknown>): Branch {
  return {
    id: String(raw.id),
    code: String(raw.code ?? ''),
    name: String(raw.name ?? ''),
    status: lower(String(raw.status)) === 'inactive' ? 'inactive' : 'active',
    timezone: String(raw.timezone ?? ''),
    phone: String(raw.phone ?? ''),
    email: String(raw.email ?? ''),
    address: String(raw.address_line1 || raw.address || raw.city || ''),
  }
}

function grantsFromContext(raw: Record<string, unknown>): Record<string, PermissionGrant> {
  const grants: Record<string, PermissionGrant> = {}
  for (const code of (raw.tenant_permissions as string[]) ?? []) {
    grants[code] = { scope: 'tenant' }
  }
  for (const branch of (raw.branches as Array<Record<string, unknown>>) ?? []) {
    const branchId = String(branch.id)
    for (const code of (branch.permissions as string[]) ?? []) {
      const existing = grants[code]
      if (existing?.scope === 'tenant') continue
      if (existing?.scope === 'branches') {
        if (!existing.branch_ids.includes(branchId)) existing.branch_ids.push(branchId)
      } else {
        grants[code] = { scope: 'branches', branch_ids: [branchId] }
      }
    }
  }
  return grants
}

function subscriptionFromEntitlements(
  entitlements: Record<string, { enabled: boolean; limit: number | null }> | undefined,
  extra?: Record<string, unknown>,
): SubscriptionSummary {
  const entries = Object.entries(entitlements ?? {})
  const status = extra?.status ? lower(String(extra.status)) : 'active'
  return {
    plan_code: extra?.plan_code ? String(extra.plan_code) : null,
    plan_name: String(extra?.plan_name ?? 'Current plan'),
    status,
    is_usable: !['suspended', 'canceled', 'cancelled', 'expired'].includes(status),
    features: entries.filter(([, value]) => value.enabled && value.limit == null).map(([code]) => code),
    max_branches: entitlements?.branches?.limit ?? null,
    max_members: entitlements?.members?.limit ?? null,
    trial_ends_at: extra?.trial_ends_at ? String(extra.trial_ends_at) : null,
  }
}

function auditSummary(row: { action: string; target_type?: string; metadata?: Record<string, unknown> }) {
  const meta = row.metadata ?? {}
  const name = meta.name ?? meta.email ?? (Array.isArray(meta.roles) ? meta.roles.join(', ') : null)
  if (name) return String(name)
  if (meta.code) return String(meta.code)
  return row.target_type || row.action
}

export async function login(email: string, password: string) {
  const { data } = await client.post<{ access: string; user: Me }>('/auth/login', { email, password })
  resetPreview()
  sessionStore.set({ accessToken: data.access, preview: false })
  return data.user
}

export async function logout() {
  if (!isPreview() && sessionStore.get().accessToken) {
    try {
      await client.post('/auth/logout')
    } catch {
      // Local session is cleared even when the API is unavailable.
    }
  }
  resetPreview()
  sessionStore.clear()
}

export async function acceptInvitation(input: { token: string; full_name: string; password: string }) {
  const { data } = await client.post<{ access: string; user: Me; organization_id?: string }>(
    '/auth/invitations/accept',
    input,
  )
  sessionStore.set({
    accessToken: data.access,
    preview: false,
    organizationId: data.organization_id ?? sessionStore.get().organizationId,
  })
  return data.user
}

export async function getMe() {
  if (isPreview()) return readPreview().me
  const { data } = await client.get<Me>('/me/')
  return {
    ...data,
    platform_permissions: data.platform_permissions ?? [],
  }
}

export async function listOrganizations(): Promise<OrganizationSummary[]> {
  if (isPreview()) return readPreview().organizations
  const { data } = await client.get<
    Array<{
      id: string
      organization: OrganizationSummary & { branding?: Branding | null }
    }>
  >('/me/organizations')
  return data.map((row) => ({
    id: row.organization.id,
    name: row.organization.name,
    slug: row.organization.slug,
    industry: lower(row.organization.industry),
    status: lower(row.organization.status) as OrgStatus,
    branding: mapBranding(row.organization.branding),
  }))
}

export async function getContext(): Promise<WorkspaceContext> {
  if (isPreview()) {
    const context = readPreview().contexts[currentOrg()]
    if (!context) throw new Error('Organization not found.')
    return context
  }
  const { data } = await client.get<Record<string, unknown>>('/me/context')
  let subscription = subscriptionFromEntitlements(
    data.entitlements as Record<string, { enabled: boolean; limit: number | null }>,
  )
  try {
    const sub = await client.get<Record<string, unknown>>('/organization/subscription')
    subscription = subscriptionFromEntitlements(
      (sub.data.entitlements as Record<string, { enabled: boolean; limit: number | null }>) ??
        (data.entitlements as Record<string, { enabled: boolean; limit: number | null }>),
      sub.data,
    )
  } catch {
    // Cashiers and similar roles may not read subscription details.
  }
  return {
    organization: mapOrganization(data.organization as Record<string, unknown>),
    branding: mapBranding(data.branding as Branding | undefined),
    subscription,
    permissions: grantsFromContext(data),
    branches: ((data.branches as Array<Record<string, unknown>>) ?? []).map(mapBranch),
  }
}

export async function createBranch(input: BranchInput) {
  if (isPreview()) return previewCreateBranch(input)
  const { data } = await client.post<Record<string, unknown>>('/branches/', {
    code: input.code,
    name: input.name,
    timezone: input.timezone,
    phone: input.phone,
    email: input.email,
    address_line1: input.address,
  })
  return mapBranch(data)
}

export async function updateOrganization(patch: Partial<Organization>) {
  if (isPreview()) return previewUpdateOrganization(patch)
  const payload: Record<string, unknown> = { ...patch }
  if (patch.address !== undefined) {
    payload.address_line1 = patch.address
    delete payload.address
  }
  if (patch.industry !== undefined) payload.industry = patch.industry.toUpperCase()
  delete payload.id
  delete payload.slug
  delete payload.status
  const { data } = await client.patch<Record<string, unknown>>('/organization/', payload)
  return mapOrganization(data)
}

export async function updateBranding(patch: Branding) {
  if (isPreview()) return previewUpdateBranding(patch)
  const { data } = await client.patch<Branding>('/organization/branding', patch)
  return mapBranding(data)
}

export async function listMembers(): Promise<Member[]> {
  if (isPreview()) return readPreview().members[currentOrg()] ?? []
  const { data } = await client.get<
    Page<{
      id: string
      status: string
      user: { full_name: string; email: string }
      roles: Array<{ role_name: string }>
      branches: Array<{ id: string; name: string }>
    }>
  >('/organization/members')
  return unwrap(data).map((row) => ({
    id: row.id,
    full_name: row.user.full_name,
    email: row.user.email,
    status: lower(row.status) === 'active' ? 'active' : 'deactivated',
    branches: row.branches.length ? row.branches.map((branch) => branch.name) : ['All branches'],
    roles: row.roles.map((role) => role.role_name),
  }))
}

export async function listInvitations(): Promise<Invitation[]> {
  if (isPreview()) return readPreview().invitations[currentOrg()] ?? []
  const [{ data }, roles] = await Promise.all([
    client.get<
      Page<{
        id: string
        email: string
        status: string
        expires_at: string
        role_assignments: Array<{ role_id?: string; scope?: string }>
      }>
    >('/organization/invitations'),
    listRoles().catch(() => [] as Role[]),
  ])
  const names = Object.fromEntries(roles.map((role) => [role.id, role.name]))
  return unwrap(data).map((row) => ({
    id: row.id,
    email: row.email,
    role_name: names[row.role_assignments?.[0]?.role_id ?? ''] ?? 'Member',
    status: lower(row.status) as Invitation['status'],
    expires_at: row.expires_at,
  }))
}

export async function sendInvitation(input: { email: string; role_id: string; branch_ids: string[] }) {
  if (isPreview()) {
    const role = (readPreview().roles[currentOrg()] ?? []).find((item) => item.id === input.role_id)
    return previewInvite(input.email, role?.name ?? 'Member')
  }
  const { data } = await client.post('/organization/invitations', {
    email: input.email,
    assignments: [
      {
        role_id: input.role_id,
        scope: input.branch_ids.length ? 'BRANCHES' : 'TENANT',
      },
    ],
    branch_ids: input.branch_ids,
  })
  return data
}

export async function revokeInvitation(id: string) {
  if (isPreview()) {
    previewRevokeInvitation(id)
    return
  }
  await client.post(`/organization/invitations/${id}/revoke`)
}

export async function listRoles(): Promise<Role[]> {
  if (isPreview()) return readPreview().roles[currentOrg()] ?? []
  const { data } = await client.get<
    Array<{
      id: string
      name: string
      description: string
      is_system: boolean
      permission_codes: string[]
    }>
  >('/organization/roles')
  return unwrap(data).map((row) => ({
    id: row.id,
    name: row.name,
    description: row.description,
    is_system: row.is_system,
    permissions: row.permission_codes,
  }))
}

export async function listAudit(search: string): Promise<AuditEvent[]> {
  if (isPreview()) {
    const rows = readPreview().audit[currentOrg()] ?? []
    const query = search.trim().toLowerCase()
    if (!query) return rows
    return rows.filter((row) => `${row.action} ${row.summary} ${row.actor_name}`.toLowerCase().includes(query))
  }
  const { data } = await client.get<
    Page<{
      id: string
      occurred_at: string
      action: string
      actor_email: string
      target_type: string
      metadata?: Record<string, unknown>
    }>
  >('/audit-events/')
  return unwrap(data)
    .map((row) => ({
      id: row.id,
      created_at: row.occurred_at,
      action: row.action,
      actor_name: row.actor_email || 'System',
      summary: auditSummary(row),
    }))
    .filter((row) => {
      const query = search.trim().toLowerCase()
      if (!query) return true
      return `${row.action} ${row.summary} ${row.actor_name}`.toLowerCase().includes(query)
    })
}

function mapPlatformTenant(row: Record<string, unknown>): PlatformTenant {
  const subscription = (row.subscription as Record<string, unknown> | null) ?? null
  const usage = (row.usage as Record<string, number> | undefined) ?? {}
  return {
    id: String(row.id),
    name: String(row.name ?? ''),
    slug: String(row.slug ?? ''),
    industry: lower(String(row.industry ?? '')),
    status: lower(String(row.status ?? '')) as OrgStatus,
    plan_name: String(subscription?.plan_name ?? '—'),
    plan_code: String(subscription?.plan_code ?? ''),
    subscription_status: lower(String(subscription?.status ?? '')),
    branch_count: Number(usage.branches ?? 0),
    member_count: Number(usage.members ?? 0),
    contact_email: String(row.contact_email ?? ''),
    legal_name: String(row.legal_name ?? ''),
  }
}

export async function listTenants(): Promise<PlatformTenant[]> {
  if (isPreview()) return readPreview().tenants
  const { data } = await client.get<Page<Record<string, unknown>>>('/platform/tenants')
  return unwrap(data).map(mapPlatformTenant)
}

export async function getPlatformMetrics(): Promise<PlatformMetrics> {
  if (isPreview()) {
    const tenants = readPreview().tenants
    return {
      total_brands: tenants.length,
      total_branches: tenants.reduce((sum, t) => sum + t.branch_count, 0),
      total_active_members: tenants.reduce((sum, t) => sum + t.member_count, 0),
      active_subscriptions: tenants.filter((t) => t.status === 'active').length,
      tenants_by_status: {},
      subscriptions_by_status: {},
      tenants_by_plan: {},
    }
  }
  const { data } = await client.get<PlatformMetrics>('/platform/metrics')
  return data
}

export async function createBrand(input: BrandOnboardInput): Promise<BrandOnboardResult> {
  if (isPreview()) {
    const tenant: PlatformTenant = {
      id: crypto.randomUUID(),
      name: input.name,
      slug: input.slug,
      industry: input.industry,
      status: 'active',
      plan_name: input.plan_code,
      plan_code: input.plan_code,
      subscription_status: 'trialing',
      branch_count: 0,
      member_count: 0,
      contact_email: input.contact_email ?? input.owner_email,
      legal_name: input.legal_name ?? '',
    }
    return {
      tenant,
      owner_invitation_url: `${window.location.origin}/invitations/accept#token=preview`,
      invitation_email_sent: true,
    }
  }
  const { data } = await client.post<{
    tenant: Record<string, unknown>
    owner_invitation_url: string
    invitation_email_sent: boolean
  }>('/platform/tenants', {
    ...input,
    industry: input.industry.toUpperCase(),
  })
  return {
    tenant: mapPlatformTenant(data.tenant),
    owner_invitation_url: data.owner_invitation_url,
    invitation_email_sent: data.invitation_email_sent,
  }
}

export async function setTenantStatus(id: string, status: OrgStatus) {
  if (isPreview()) {
    previewSetTenantStatus(id, status)
    return
  }
  await client.post(`/platform/tenants/${id}/status`, {
    status: status.toUpperCase(),
    reason: 'Updated from platform administration',
  })
}

export async function setTenantSubscription(
  id: string,
  patch: { plan_code?: string; status?: string },
) {
  if (isPreview()) return
  await client.patch(`/platform/tenants/${id}/subscription`, {
    ...patch,
    status: patch.status?.toUpperCase(),
  })
}

function mapExpense(row: Record<string, unknown>): Expense {
  return {
    id: String(row.id),
    branch_id: String(row.branch_id ?? ''),
    branch_name: String(row.branch_name ?? ''),
    category_id: String(row.category_id ?? ''),
    category_name: String(row.category_name ?? ''),
    entry_type: lower(String(row.entry_type)) === 'recurring' ? 'recurring' : 'variable',
    status: lower(String(row.status)) as ExpenseStatus,
    amount: String(row.amount ?? '0'),
    expense_date: String(row.expense_date ?? ''),
    billing_period: String(row.billing_period ?? ''),
    payment_method: String(row.payment_method ?? ''),
    description: String(row.description ?? ''),
    receipt_url: row.receipt_url ? String(row.receipt_url) : null,
    submitted_by_email: String(row.submitted_by_email ?? ''),
    submitted_by_name: String(row.submitted_by_name ?? ''),
    submitted_at: row.submitted_at ? String(row.submitted_at) : null,
    approved_by_email: String(row.approved_by_email ?? ''),
    approved_at: row.approved_at ? String(row.approved_at) : null,
    rejected_at: row.rejected_at ? String(row.rejected_at) : null,
    rejection_reason: String(row.rejection_reason ?? ''),
    paid_at: row.paid_at ? String(row.paid_at) : null,
    payment_reference: String(row.payment_reference ?? ''),
    created_at: String(row.created_at ?? ''),
  }
}

export async function listExpenses(params: { status?: string; search?: string } = {}) {
  if (isPreview()) return []
  const { data } = await client.get<Page<Record<string, unknown>>>('/expenses/', {
    params: {
      status: params.status?.toUpperCase(),
      search: params.search || undefined,
    },
  })
  return unwrap(data).map(mapExpense)
}

export async function getExpense(id: string) {
  const { data } = await client.get<Record<string, unknown>>(`/expenses/${id}/`)
  return mapExpense(data)
}

export async function createExpense(input: {
  branch_id: string
  category_id: string
  amount: string
  expense_date: string
  payment_method: string
  description: string
  receipt?: File | null
}) {
  const body = new FormData()
  body.append('branch_id', input.branch_id)
  body.append('category_id', input.category_id)
  body.append('amount', input.amount)
  body.append('expense_date', input.expense_date)
  body.append('payment_method', input.payment_method)
  body.append('description', input.description)
  if (input.receipt) body.append('receipt', input.receipt)
  const { data } = await client.post<Record<string, unknown>>('/expenses/', body)
  return mapExpense(data)
}

export async function submitExpense(id: string) {
  const { data } = await client.post<Record<string, unknown>>(`/expenses/${id}/submit/`)
  return mapExpense(data)
}

export async function approveExpense(id: string) {
  const { data } = await client.post<Record<string, unknown>>(`/expenses/${id}/approve/`)
  return mapExpense(data)
}

export async function rejectExpense(id: string, reason: string) {
  const { data } = await client.post<Record<string, unknown>>(`/expenses/${id}/reject/`, { reason })
  return mapExpense(data)
}

export async function markExpensePaid(id: string, payment_reference = '') {
  const { data } = await client.post<Record<string, unknown>>(`/expenses/${id}/mark-paid/`, {
    payment_reference,
  })
  return mapExpense(data)
}

export async function getExpenseSummary(): Promise<ExpenseSummary> {
  if (isPreview()) {
    return {
      pending_approval: 0,
      draft: 0,
      approved: 0,
      rejected: 0,
      paid: 0,
      total_pending_amount: '0',
    }
  }
  const { data } = await client.get<ExpenseSummary>('/expenses/summary')
  return {
    ...data,
    total_pending_amount: String(data.total_pending_amount ?? '0'),
  }
}

export async function getExpenseReport(): Promise<ExpenseReportRow[]> {
  if (isPreview()) return []
  const { data } = await client.get<ExpenseReportRow[]>('/expenses/reports/by-branch')
  return data.map((row) => ({
    ...row,
    status: lower(row.status),
    total_amount: String(row.total_amount ?? '0'),
  }))
}

export async function listExpenseCategories(): Promise<ExpenseCategory[]> {
  if (isPreview()) return []
  const { data } = await client.get<Page<ExpenseCategory>>('/expenses/categories/')
  return unwrap(data)
}

export async function createExpenseCategory(input: { code: string; name: string }) {
  const { data } = await client.post<ExpenseCategory>('/expenses/categories/', input)
  return data
}

export async function listRecurringExpenses(): Promise<RecurringExpense[]> {
  if (isPreview()) return []
  const { data } = await client.get<Page<Record<string, unknown>>>('/expenses/recurring/')
  return unwrap(data).map((row) => ({
    id: String(row.id),
    branch_id: String(row.branch_id),
    branch_name: String(row.branch_name ?? ''),
    category_id: String(row.category_id),
    category_name: String(row.category_name ?? ''),
    expected_amount: String(row.expected_amount ?? '0'),
    frequency: String(row.frequency ?? 'MONTHLY'),
    start_date: String(row.start_date ?? ''),
    end_date: row.end_date ? String(row.end_date) : null,
    due_day: Number(row.due_day ?? 1),
    description: String(row.description ?? ''),
    is_active: Boolean(row.is_active),
  }))
}

export async function createRecurringExpense(input: {
  branch_id: string
  category_id: string
  expected_amount: string
  start_date: string
  end_date?: string
  due_day: number
  description: string
}) {
  const { data } = await client.post('/expenses/recurring/', {
    ...input,
    frequency: 'MONTHLY',
    is_active: true,
  })
  return data
}

export async function listNotifications(): Promise<AppNotification[]> {
  if (isPreview()) return []
  const { data } = await client.get<Page<Record<string, unknown>>>('/notifications/')
  return unwrap(data).map((row) => ({
    id: String(row.id),
    notification_type: String(row.notification_type ?? ''),
    title: String(row.title ?? ''),
    body: String(row.body ?? ''),
    link_path: String(row.link_path ?? ''),
    expense_id: row.expense_id ? String(row.expense_id) : null,
    is_read: Boolean(row.is_read),
    read_at: row.read_at ? String(row.read_at) : null,
    created_at: String(row.created_at ?? ''),
  }))
}

export async function getUnreadNotificationCount(): Promise<number> {
  if (isPreview()) return 0
  const { data } = await client.get<{ unread_count: number }>('/notifications/unread-count/')
  return data.unread_count
}

export async function markNotificationRead(id: string) {
  await client.post(`/notifications/${id}/mark-read/`)
}

export async function markAllNotificationsRead() {
  await client.post('/notifications/mark-all-read/')
}

export async function getNotificationSettings(): Promise<NotificationSettings> {
  if (isPreview()) {
    return {
      primary_email: '',
      extra_recipient_emails: [],
      reminder_intervals_hours: [24, 48],
      reminders_enabled: true,
    }
  }
  const { data } = await client.get<NotificationSettings>('/notifications/settings')
  return data
}

export async function updateNotificationSettings(patch: Partial<NotificationSettings>) {
  const { data } = await client.patch<NotificationSettings>('/notifications/settings', patch)
  return data
}

export async function listPlans(): Promise<Plan[]> {
  if (isPreview()) return readPreview().plans
  const { data } = await client.get<
    Array<{
      id: string
      code: string
      name: string
      description: string
      trial_days: number
      is_active: boolean
      entitlements: Array<{ feature_code: string; enabled: boolean; limit_value: number | null }>
    }>
  >('/platform/plans')
  return unwrap(data).map((row) => ({
    id: row.id,
    code: row.code,
    name: row.name,
    description: row.description,
    trial_days: row.trial_days,
    is_active: row.is_active,
    max_branches: row.entitlements?.find((item) => item.feature_code === 'branches')?.limit_value ?? null,
    max_members: row.entitlements?.find((item) => item.feature_code === 'members')?.limit_value ?? null,
    features: (row.entitlements ?? [])
      .filter((item) => item.enabled && item.limit_value == null)
      .map((item) => item.feature_code),
  }))
}
