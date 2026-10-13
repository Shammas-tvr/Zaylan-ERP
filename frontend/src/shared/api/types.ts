export type OrgStatus = 'pending' | 'active' | 'suspended' | 'deactivated'

export type Branding = {
  display_name: string
  logo_url: string
  primary_color: string
  secondary_color: string
  background_color: string
  surface_color: string
  text_color: string
}

export type Organization = {
  id: string
  name: string
  legal_name: string
  slug: string
  industry: string
  status: OrgStatus
  currency: string
  timezone: string
  locale: string
  tax_registration_number: string
  prices_include_tax: boolean
  contact_email: string
  contact_phone: string
  address: string
}

export type OrganizationSummary = {
  id: string
  name: string
  slug: string
  industry: string
  status: OrgStatus
  branding: Branding
}

export type Branch = {
  id: string
  code: string
  name: string
  status: 'active' | 'inactive'
  timezone: string
  phone: string
  email: string
  address: string
}

export type BranchInput = {
  name: string
  code: string
  timezone: string
  phone: string
  email: string
  address: string
}

export type PermissionGrant =
  | { scope: 'tenant' }
  | { scope: 'branches'; branch_ids: string[] }

export type SubscriptionSummary = {
  plan_code: string | null
  plan_name: string
  status: string | null
  is_usable: boolean
  features: string[]
  max_branches: number | null
  max_members: number | null
  trial_ends_at: string | null
}

export type WorkspaceContext = {
  organization: Organization
  branding: Branding
  subscription: SubscriptionSummary
  permissions: Record<string, PermissionGrant>
  branches: Branch[]
}

export type Me = {
  id: string
  email: string
  username?: string | null
  full_name: string
  platform_permissions: string[]
}

export type Member = {
  id: string
  full_name: string
  email: string
  status: 'active' | 'deactivated'
  branches: string[]
  roles: string[]
}

export type Invitation = {
  id: string
  email: string
  role_name: string
  status: 'pending' | 'accepted' | 'revoked'
  expires_at: string
}

export type Role = {
  id: string
  name: string
  description: string
  is_system: boolean
  permissions: string[]
}

export type AuditEvent = {
  id: string
  created_at: string
  action: string
  actor_name: string
  summary: string
}

export type PlatformTenant = {
  id: string
  name: string
  slug: string
  industry: string
  status: OrgStatus
  plan_name: string
  plan_code: string
  subscription_status: string
  branch_count: number
  member_count: number
  contact_email: string
  legal_name: string
  portal_url: string
}

export type PlatformMetrics = {
  total_brands: number
  total_branches: number
  total_active_members: number
  active_subscriptions: number
  tenants_by_status: Record<string, number>
  subscriptions_by_status: Record<string, number>
  tenants_by_plan: Record<string, number>
}

export type BrandOnboardInput = {
  name: string
  slug: string
  industry: string
  plan_code: string
  owner_email: string
  owner_password: string
  owner_full_name?: string
  legal_name?: string
  contact_phone?: string
  currency?: string
  timezone?: string
  country?: string
  locale?: string
}

export type BrandOnboardResult = {
  tenant: PlatformTenant
  brand_admin_email: string
  portal_url: string
}

export type ExpenseStatus = 'draft' | 'pending_approval' | 'approved' | 'rejected' | 'paid'

export type Expense = {
  id: string
  branch_id: string
  branch_name: string
  category_id: string
  category_name: string
  entry_type: 'recurring' | 'variable'
  status: ExpenseStatus
  amount: string
  expense_date: string
  billing_period: string
  payment_method: string
  description: string
  receipt_url: string | null
  submitted_by_email: string
  submitted_by_name: string
  submitted_at: string | null
  approved_by_email: string
  approved_at: string | null
  rejected_at: string | null
  rejection_reason: string
  paid_at: string | null
  payment_reference: string
  created_at: string
}

export type ExpenseCategory = {
  id: string
  code: string
  name: string
  is_active: boolean
}

export type RecurringExpense = {
  id: string
  branch_id: string
  branch_name: string
  category_id: string
  category_name: string
  expected_amount: string
  frequency: string
  start_date: string
  end_date: string | null
  due_day: number
  description: string
  is_active: boolean
}

export type ExpenseSummary = {
  pending_approval: number
  draft: number
  approved: number
  rejected: number
  paid: number
  total_pending_amount: string
}

export type ExpenseReportRow = {
  branch_id: string
  branch_name: string
  status: string
  count: number
  total_amount: string
}

export type AppNotification = {
  id: string
  notification_type: string
  title: string
  body: string
  link_path: string
  expense_id: string | null
  is_read: boolean
  read_at: string | null
  created_at: string
}

export type NotificationSettings = {
  primary_email: string
  extra_recipient_emails: string[]
  reminder_intervals_hours: number[]
  reminders_enabled: boolean
}

export type Plan = {
  id: string
  code: string
  name: string
  description: string
  trial_days: number
  max_branches: number | null
  max_members: number | null
  features: string[]
  is_active: boolean
}

export type Page<T> = {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
