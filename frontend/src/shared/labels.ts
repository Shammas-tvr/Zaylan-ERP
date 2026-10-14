export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(' ')
}

export const industryLabel: Record<string, string> = {
  dessert_shop: 'Dessert shop',
  bakery: 'Bakery',
  cafe: 'Cafe',
  restaurant: 'Restaurant',
  retail: 'Retail',
  other: 'Other',
}

export const statusLabel: Record<string, string> = {
  pending: 'Pending',
  active: 'Active',
  suspended: 'Suspended',
  deactivated: 'Deactivated',
  inactive: 'Inactive',
  trialing: 'Trial',
  past_due: 'Past due',
  canceled: 'Canceled',
  expired: 'Expired',
  accepted: 'Accepted',
  revoked: 'Revoked',
  draft: 'Draft',
  pending_approval: 'Pending approval',
  approved: 'Approved',
  dispatched: 'Dispatched',
  received: 'Received',
  partially_received: 'Partially received',
  closed: 'Closed',
  completed: 'Completed',
  refunded: 'Refunded',
  voided: 'Voided',
  rejected: 'Rejected',
  paid: 'Paid',
  normal: 'Normal',
  low: 'Low stock',
  out: 'Out of stock',
  unstocked: 'Not stocked',
}

export const featureLabel: Record<string, string> = {
  multi_branch: 'Multiple branches',
  branches: 'Multiple branches',
  members: 'People',
  custom_roles: 'Custom roles',
  custom_branding: 'Custom branding',
  audit_log: 'Audit log',
  products: 'Products and catalog',
  pos: 'Point of sale',
  recipes: 'Recipes and costing',
  inventory: 'Inventory',
  purchasing: 'Purchasing',
  production: 'Production',
  expenses: 'Expenses',
  finance_reports: 'Financial reports',
  franchise: 'Franchise profit sharing',
}

export const actionLabel: Record<string, string> = {
  'branch.created': 'Branch created',
  'branch.updated': 'Branch updated',
  'branches.created': 'Branch created',
  'branches.updated': 'Branch updated',
  'member.invited': 'Invitation sent',
  'member.invitation_revoked': 'Invitation revoked',
  'members.invited': 'Invitation sent',
  'members.invitation_revoked': 'Invitation revoked',
  'members.invitation_accepted': 'Invitation accepted',
  'organization.updated': 'Organization updated',
  'organization.settings_updated': 'Organization updated',
  'organization.branding_updated': 'Branding updated',
  'platform.tenant_status_changed': 'Tenant status changed',
}

export function labelOf(map: Record<string, string>, code: string) {
  return map[code] ?? code.replace(/_/g, ' ')
}

export function formatWhen(value: string, timeZone = 'Asia/Kolkata') {
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone,
  }).format(new Date(value))
}

export function formatDate(value: string, timeZone = 'Asia/Kolkata') {
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeZone }).format(new Date(value))
}

export function initials(name: string) {
  const parts = name.trim().split(/\s+/).slice(0, 2)
  return parts.map((part) => part[0]?.toUpperCase() ?? '').join('') || 'Z'
}
