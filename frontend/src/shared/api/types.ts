export type ApiErrorBody = {
  error: { code: string; message: string; details?: unknown; request_id?: string }
}

export type Paginated<T> = {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type User = {
  id: string
  email: string
  full_name: string
  date_joined?: string
  platform_permissions?: string[]
}

export type Session = {
  access: string
  user: User
  organization_id?: string
}

export type Branding = {
  display_name: string
  logo_url: string
  primary_color: string
  secondary_color: string
  background_color: string
  surface_color: string
  text_color: string
}

export type OrganizationSummary = {
  id: string
  slug: string
  name: string
  industry: string
  status: string
  branding?: Branding
}

export type MembershipSummary = {
  id: string
  organization: OrganizationSummary
  is_owner: boolean
  status: string
  joined_at: string
}

export type Organization = {
  id: string
  slug: string
  name: string
  legal_name: string
  industry: string
  status: string
  currency: string
  timezone: string
  locale: string
  country: string
  tax_registration_number: string
  prices_include_tax: boolean
  contact_email: string
  contact_phone: string
  address_line1: string
  address_line2: string
  city: string
  state: string
  postal_code: string
  onboarding_status: string
}

export type BranchAccess = {
  id: string
  code: string
  name: string
  status: string
  permissions: string[]
}

export type Entitlement = { enabled: boolean; limit: number | null }

export type TenantContext = {
  organization: Organization
  branding: Branding
  membership: { id: string; is_owner: boolean }
  tenant_permissions: string[]
  branches: BranchAccess[]
  entitlements: Record<string, Entitlement>
}

export type Branch = {
  id: string
  code: string
  name: string
  status: string
  timezone: string
  phone: string
  email: string
  address_line1: string
  city: string
  state: string
  postal_code: string
}

export type Member = {
  id: string
  user: User
  status: string
  is_owner: boolean
  joined_at: string
  roles: { role_id: string; role_name: string; scope: string }[]
  branches: { id: string; code: string; name: string }[]
}

export type Role = {
  id: string
  key: string
  name: string
  description: string
  is_system: boolean
  permission_codes: string[]
  member_count: number
}

export type Invitation = {
  id: string
  email: string
  status: string
  is_owner: boolean
  expires_at: string
  created_at: string
  is_expired: boolean
}

export type PlatformTenant = {
  id: string
  slug: string
  name: string
  industry: string
  status: string
  onboarding_status: string
  created_at: string
  subscription: {
    plan_code: string
    plan_name: string
    status: string
    trial_ends_at: string | null
  } | null
}

export type Plan = {
  id: string
  code: string
  name: string
  description: string
  is_active: boolean
  trial_days: number
  tenant_count: number
}

export type PlatformMetrics = {
  tenants_by_status: Record<string, number>
  subscriptions_by_status: Record<string, number>
  tenants_by_plan: Record<string, number>
  total_branches: number
  total_active_members: number
}

export type AuditEvent = {
  id: string
  occurred_at: string
  actor_email: string
  action: string
  target_type: string
  target_id: string
  metadata: Record<string, unknown>
}
