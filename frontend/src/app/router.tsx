import { useEffect } from 'react'
import { Navigate, Outlet, RouterProvider, createBrowserRouter, useLocation } from 'react-router-dom'

import { AcceptInvitationPage } from '../features/authentication/AcceptInvitationPage'
import { useAuth, useOrganizations } from '../features/authentication/AuthProvider'
import { LoginPage } from '../features/authentication/LoginPage'
import { BranchesPage } from '../features/branches/BranchesPage'
import { PlatformPage } from '../features/platform_admin/PlatformPage'
import { SettingsPage } from '../features/settings/SettingsPage'
import { DashboardPage } from '../features/tenant_dashboard/DashboardPage'
import { ChooseOrganizationPage } from '../features/tenant_switcher/ChooseOrganizationPage'
import { TenantProvider } from '../features/tenant_switcher/TenantProvider'
import { TeamPage } from '../features/users_roles/TeamPage'
import { Button } from '../shared/components/ui'
import { AppShell } from './AppShell'

function RequireAuth() {
  const { user, ready } = useAuth()
  const location = useLocation()
  if (!ready) return <p className="p-8 text-sm">Restoring session…</p>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

function RequireTenant() {
  const { organizationId, user, selectOrganization } = useAuth()
  const { data: memberships, isLoading } = useOrganizations()
  const first = memberships?.[0]?.organization.id

  useEffect(() => {
    if (!organizationId && first) selectOrganization(first)
  }, [first, organizationId, selectOrganization])

  if (isLoading) return <p className="p-8 text-sm">Loading organizations…</p>
  if (!organizationId) {
    if (first) return <p className="p-8 text-sm">Opening organization…</p>
    if (user?.platform_permissions?.length) return <Navigate to="/platform" replace />
    return <ChooseOrganizationPage />
  }
  return (
    <TenantProvider>
      <AppShell />
    </TenantProvider>
  )
}

function RequirePlatform() {
  const { user, signOut, organizationId } = useAuth()
  if (!user?.platform_permissions?.length) return <Navigate to="/" replace />
  return (
    <div className="min-h-screen bg-cream">
      <header className="flex items-center justify-between border-b border-line bg-surface px-6 py-3">
        <p className="font-display text-lg font-semibold text-burgundy">Zaylan platform</p>
        <div className="flex items-center gap-3 text-sm">
          {organizationId ? <a className="font-semibold text-burgundy" href="/">Back to organization</a> : null}
          <Button variant="ghost" onClick={() => signOut()}>Sign out</Button>
        </div>
      </header>
      <div className="px-4 py-6 sm:px-8">
        <PlatformPage />
      </div>
    </div>
  )
}

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/invitations/accept', element: <AcceptInvitationPage /> },
  {
    element: <RequireAuth />,
    children: [
      { path: '/platform', element: <RequirePlatform /> },
      {
        element: <RequireTenant />,
        children: [
          { path: '/', element: <DashboardPage /> },
          { path: '/branches', element: <BranchesPage /> },
          { path: '/team', element: <TeamPage /> },
          { path: '/settings', element: <SettingsPage /> },
        ],
      },
    ],
  },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
