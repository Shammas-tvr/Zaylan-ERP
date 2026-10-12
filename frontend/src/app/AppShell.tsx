import { NavLink, Outlet } from 'react-router-dom'
import { Building2, LayoutDashboard, LogOut, Settings, Shield, Users } from 'lucide-react'

import { useAuth, useOrganizations } from '../features/authentication/AuthProvider'
import { can, useTenant } from '../features/tenant_switcher/TenantProvider'
import { Button } from '../shared/components/ui'

const links = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, permission: null },
  { to: '/branches', label: 'Branches', icon: Building2, permission: 'branches.view' },
  { to: '/team', label: 'Team', icon: Users, permission: 'members.view' },
  { to: '/settings', label: 'Settings', icon: Settings, permission: 'organization.view' },
]

export function AppShell() {
  const { user, signOut, selectOrganization, organizationId } = useAuth()
  const { data: memberships = [] } = useOrganizations()
  const tenant = useTenant()
  const platform = Boolean(user?.platform_permissions?.length)

  return (
    <div className="min-h-screen bg-cream text-ink">
      <div className="grid min-h-screen lg:grid-cols-[16rem_1fr]">
        <aside className="border-b border-line bg-surface lg:border-b-0 lg:border-r">
          <div className="flex items-center gap-3 px-5 py-5">
            <span className="h-8 w-8 rounded-full bg-burgundy" aria-hidden />
            <div>
              <p className="font-display text-lg font-semibold leading-none">
                {tenant.branding.display_name || tenant.organization.name}
              </p>
              <p className="mt-1 text-xs uppercase tracking-wide text-tan">Zaylan</p>
            </div>
          </div>
          <nav className="flex flex-col gap-1 px-3 pb-6">
            {links
              .filter((link) => !link.permission || can(tenant, link.permission))
              .map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.to === '/'}
                  className={({ isActive }) =>
                    `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
                      isActive ? 'bg-burgundy/10 text-burgundy' : 'text-ink/80 hover:bg-cream'
                    }`
                  }
                >
                  <link.icon size={16} aria-hidden />
                  {link.label}
                </NavLink>
              ))}
            {platform ? (
              <NavLink
                to="/platform"
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
                    isActive ? 'bg-burgundy/10 text-burgundy' : 'text-ink/80 hover:bg-cream'
                  }`
                }
              >
                <Shield size={16} aria-hidden />
                Platform
              </NavLink>
            ) : null}
          </nav>
        </aside>
        <div className="flex min-w-0 flex-col">
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface px-6 py-3">
            <label className="text-sm">
              <span className="sr-only">Organization</span>
              <select
                className="rounded-lg border border-line bg-cream px-3 py-2"
                value={organizationId || ''}
                onChange={(event) => selectOrganization(event.target.value)}
              >
                {memberships.map((m) => (
                  <option key={m.organization.id} value={m.organization.id}>
                    {m.organization.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex items-center gap-3 text-sm">
              <span>{user?.full_name}</span>
              <Button variant="ghost" onClick={() => signOut()}>
                <LogOut size={16} className="mr-1" /> Sign out
              </Button>
            </div>
          </header>
          <main className="flex-1 px-4 py-6 sm:px-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
