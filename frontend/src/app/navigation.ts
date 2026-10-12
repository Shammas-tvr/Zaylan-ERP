export const workspaceNav = [
  { to: '/', label: 'Overview', permission: null, end: true },
  { to: '/branches', label: 'Branches', permission: 'branches.view', end: false },
  { to: '/expenses', label: 'Expenses', permission: 'expenses.view', end: false },
  { to: '/expenses/approvals', label: 'Approvals', permission: 'expenses.approve', end: false },
  { to: '/expenses/recurring', label: 'Recurring', permission: 'expenses.configure', end: false },
  { to: '/expenses/reports', label: 'Expense reports', permission: 'expenses.view', end: false },
  { to: '/people', label: 'People', permission: 'members.view', end: false },
  { to: '/settings', label: 'Settings', permission: 'organization.view', end: false },
  { to: '/audit', label: 'Audit', permission: 'audit.view', end: false },
] as const

export const platformNav = [
  { to: '/platform/brands', label: 'Brands', permission: 'platform.tenants.view' },
  { to: '/platform/plans', label: 'Plans', permission: 'platform.plans.view' },
] as const
