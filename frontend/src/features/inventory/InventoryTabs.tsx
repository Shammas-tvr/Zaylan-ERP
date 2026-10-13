import { NavLink, Outlet } from 'react-router-dom'
import { Box, BookOpen, Factory, Truck, Warehouse } from 'lucide-react'
import { usePageTitle } from '../../shared/hooks.ts'
import { can } from '../../shared/permissions.ts'
import { NoAccess } from '../../shared/ui/Feedback.tsx'
import { useWorkspace } from '../workspace/queries.ts'

const tabs = [
  { to: '/inventory', label: 'Items', icon: Box, permission: 'inventory.view', end: true },
  { to: '/inventory/recipes', label: 'Recipes', icon: BookOpen, permission: 'catalog.view', end: false },
  { to: '/inventory/production', label: 'Production', icon: Factory, permission: 'production.manage', end: false },
  { to: '/inventory/transfers', label: 'Transfers', icon: Truck, permission: 'inventory.view', end: false },
  { to: '/inventory/stock', label: 'Stock', icon: Warehouse, permission: 'inventory.view', end: false },
]

export function InventoryTabs() {
  usePageTitle('Inventory')
  const workspace = useWorkspace()
  const context = workspace.data
  if (!context) return null
  if (!can(context.permissions, 'inventory.view')) return <NoAccess />

  const visibleTabs = tabs.filter((tab) => can(context.permissions, tab.permission))

  return (
    <div className="grid gap-6">
      <nav aria-label="Inventory sections" className="flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line">
        {visibleTabs.map((tab) => {
          const Icon = tab.icon
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                `-mb-px flex shrink-0 items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                  isActive
                    ? 'border-[var(--brand-primary)] text-[var(--brand-primary)]'
                    : 'border-transparent text-ink-soft hover:text-ink'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </NavLink>
          )
        })}
      </nav>
      <Outlet />
    </div>
  )
}
