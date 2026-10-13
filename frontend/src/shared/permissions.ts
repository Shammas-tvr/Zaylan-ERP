import type { PermissionGrant } from './api/types.ts'

export const permissionCatalog: Record<string, { name: string; category: string }> = {
  'organization.view': { name: 'View organization', category: 'Organization' },
  'organization.manage': { name: 'Manage organization', category: 'Organization' },
  'subscription.view': { name: 'View subscription', category: 'Organization' },
  'branches.view': { name: 'View branches', category: 'Branches' },
  'branches.manage': { name: 'Manage branches', category: 'Branches' },
  'members.view': { name: 'View members', category: 'People' },
  'members.manage': { name: 'Manage members', category: 'People' },
  'roles.view': { name: 'View roles', category: 'People' },
  'roles.manage': { name: 'Manage roles', category: 'People' },
  'audit.view': { name: 'View audit history', category: 'Audit' },
  'catalog.view': { name: 'View products and prices', category: 'Catalog' },
  'catalog.manage': { name: 'Manage products and prices', category: 'Catalog' },
  'costs.view': { name: 'View costs and recipes', category: 'Catalog' },
  'costs.manage': { name: 'Manage costs and recipes', category: 'Catalog' },
  'pos.sell': { name: 'Sell at the point of sale', category: 'Sales' },
  'pos.refund': { name: 'Authorize refunds and voids', category: 'Sales' },
  'sales.view_own': { name: 'View own sales and shift', category: 'Sales' },
  'sales.view': { name: 'View sales records', category: 'Sales' },
  'sales.totals.view': { name: 'View sales totals', category: 'Sales' },
  'inventory.view': { name: 'View inventory', category: 'Inventory' },
  'inventory.manage': { name: 'Manage inventory', category: 'Inventory' },
  'inventory.dispatch': { name: 'Dispatch stock from the kitchen', category: 'Inventory' },
  'inventory.receive': { name: 'Confirm stock received at a branch', category: 'Inventory' },
  'inventory.adjust': { name: 'Adjust inventory', category: 'Inventory' },
  'production.manage': { name: 'Manage central kitchen production', category: 'Production' },
  'purchasing.manage': { name: 'Manage purchasing', category: 'Inventory' },
  'expenses.submit': { name: 'Submit expenses', category: 'Expenses' },
  'expenses.view': { name: 'View expenses', category: 'Expenses' },
  'expenses.approve': { name: 'Approve expenses', category: 'Expenses' },
  'expenses.pay': { name: 'Record expense payments', category: 'Expenses' },
  'expenses.configure': { name: 'Configure expenses', category: 'Expenses' },
  'reports.financial.view': { name: 'View financial reports', category: 'Finance' },
}

export function can(
  permissions: Record<string, PermissionGrant> | undefined,
  code: string,
  branchId?: string | null,
) {
  const grant = permissions?.[code]
  if (!grant) return false
  if (grant.scope === 'tenant') return true
  if (!branchId) return grant.branch_ids.length > 0
  return grant.branch_ids.includes(branchId)
}

export function canPlatform(permissions: string[] | undefined, code: string) {
  return Boolean(permissions?.includes(code))
}
