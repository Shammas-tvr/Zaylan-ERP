import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { logout } from '../shared/api/workspace.ts'
import { queryClient } from '../shared/api/queryClient.ts'
import { brandVars, defaultBranding } from '../shared/brand.ts'
import { cn, formatWhen, industryLabel, labelOf } from '../shared/labels.ts'
import { can, canPlatform } from '../shared/permissions.ts'
import { ErrorState, PageSkeleton } from '../shared/ui/Feedback.tsx'
import { MenuButton, Wordmark } from '../shared/ui/Wordmark.tsx'
import { platformNav, workspaceNav } from './navigation.ts'
import {
  selectBranch,
  selectOrganization,
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useMe,
  useNotifications,
  useOrganizations,
  useSession,
  useUnreadNotificationCount,
  useWorkspace,
} from '../features/workspace/queries.ts'

export function WorkspaceLayout() {
  const session = useSession()
  const organizations = useOrganizations()
  const workspace = useWorkspace()
  const me = useMe()
  const navigate = useNavigate()
  const [navOpen, setNavOpen] = useState(false)
  const [previewNote, setPreviewNote] = useState(session.preview)
  const desktopNav = useDesktopNav()

  useEffect(() => {
    if (!session.organizationId && organizations.data && organizations.data.length > 0) {
      selectOrganization(organizations.data[0].id)
    }
  }, [organizations.data, session.organizationId])

  const summary = organizations.data?.find((item) => item.id === session.organizationId)
  const branding = workspace.data?.branding ?? summary?.branding ?? defaultBranding
  const permissions = workspace.data?.permissions
  const branches = workspace.data?.branches ?? []

  async function signOut() {
    await logout()
    queryClient.clear()
    navigate('/login')
  }

  return (
    <div style={brandVars(branding)} className="min-h-svh bg-[var(--brand-background)] text-[var(--brand-text)]">
      <div className="mx-auto flex min-h-svh max-w-[1440px]">
        {navOpen ? (
          <button className="fixed inset-0 z-30 bg-ink/30 lg:hidden" aria-label="Close navigation" onClick={() => setNavOpen(false)} />
        ) : null}
        <aside
          inert={!desktopNav && !navOpen}
          className={cn(
            'fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-line bg-[var(--brand-surface)] px-4 py-5 transition-transform lg:static lg:translate-x-0',
            navOpen ? 'translate-x-0' : '-translate-x-full',
          )}
        >
          <Wordmark />
          <span className="mt-4 h-0.5 w-10 bg-[var(--brand-secondary)]" />
          <label className="mt-6 grid gap-1.5 text-sm">
            <span className="text-ink-soft">Organization</span>
            <select
              className="h-11 rounded-xl border border-line bg-cream px-3"
              value={session.organizationId ?? ''}
              onChange={(event) => {
                selectOrganization(event.target.value)
                setNavOpen(false)
              }}
            >
              {(organizations.data ?? []).map((organization) => (
                <option key={organization.id} value={organization.id}>
                  {organization.name}
                </option>
              ))}
            </select>
          </label>
          <nav className="mt-6 grid gap-1" aria-label="Workspace">
            {workspaceNav
              .filter((item) => item.permission === null || can(permissions, item.permission))
              .map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={() => setNavOpen(false)}
                  className={({ isActive }) =>
                    cn(
                      'rounded-xl border-l-2 px-3 py-2.5 text-sm',
                      isActive
                        ? 'border-[var(--brand-primary)] bg-cream font-medium text-[var(--brand-primary)]'
                        : 'border-transparent text-ink hover:bg-cream',
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
          </nav>
          {platformNav.some((item) => canPlatform(me.data?.platform_permissions, item.permission)) ? (
            <div className="mt-6">
              <p className="px-3 text-xs font-medium tracking-wide text-ink-soft">Platform</p>
              <nav className="mt-2 grid gap-1" aria-label="Platform">
                {platformNav
                  .filter((item) => canPlatform(me.data?.platform_permissions, item.permission))
                  .map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      onClick={() => setNavOpen(false)}
                      className={({ isActive }) =>
                        cn(
                          'rounded-xl border-l-2 px-3 py-2.5 text-sm',
                          isActive
                            ? 'border-[var(--brand-primary)] bg-cream font-medium text-[var(--brand-primary)]'
                            : 'border-transparent text-ink hover:bg-cream',
                        )
                      }
                    >
                      {item.label}
                    </NavLink>
                  ))}
              </nav>
            </div>
          ) : null}
          <div className="mt-auto border-t border-line pt-4">
            <p className="truncate text-sm font-medium">{me.data?.full_name}</p>
            <p className="truncate text-sm text-ink-soft">{me.data?.email}</p>
            <button type="button" className="mt-3 text-sm font-medium text-[var(--brand-primary)]" onClick={() => void signOut()}>
              Sign out
            </button>
          </div>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center gap-3 border-b border-line/80 px-4 py-3 sm:px-8">
            <MenuButton open={navOpen} onClick={() => setNavOpen(true)} />
            <p className="hidden text-sm text-ink-soft sm:block">
              {summary ? labelOf(industryLabel, summary.industry) : 'Workspace'}
            </p>
            <div className="ml-auto flex items-center gap-3">
              {session.organizationId ? <NotificationBell /> : null}
              <label className="grid">
                <span className="sr-only">Branch</span>
                <select
                  className="h-11 rounded-xl border border-line bg-[var(--brand-surface)] px-3 text-sm"
                  value={session.branchId ?? ''}
                  onChange={(event) => selectBranch(event.target.value || null)}
                >
                  <option value="">All branches</option>
                  {branches.map((branch) => (
                    <option key={branch.id} value={branch.id}>
                      {branch.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </header>
          <main className="flex-1 px-4 py-6 sm:px-8 sm:py-8">
            <div className="mx-auto grid max-w-6xl gap-6">
              {previewNote ? (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-[var(--brand-surface)] px-4 py-3 text-sm">
                  <p>Sample workspace. Changes here stay in this browser and are not saved to a business.</p>
                  <button type="button" className="font-medium text-[var(--brand-primary)]" onClick={() => setPreviewNote(false)}>
                    Hide
                  </button>
                </div>
              ) : null}
              <WorkspaceBody
                isLoading={workspace.isLoading || organizations.isLoading}
                isError={workspace.isError}
                error={workspace.error}
                onRetry={() => void workspace.refetch()}
                hasOrganization={Boolean(session.organizationId)}
              />
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}

function NotificationBell() {
  const [open, setOpen] = useState(false)
  const unread = useUnreadNotificationCount()
  const notifications = useNotifications()
  const markRead = useMarkNotificationRead()
  const markAll = useMarkAllNotificationsRead()
  const count = unread.data ?? 0

  return (
    <div className="relative">
      <button
        type="button"
        className="relative flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-[var(--brand-surface)] text-sm"
        aria-label={`Notifications${count ? `, ${count} unread` : ''}`}
        onClick={() => setOpen((value) => !value)}
      >
        Bell
        {count > 0 ? (
          <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--brand-primary)] px-1 text-[10px] font-medium text-cream">
            {count > 99 ? '99+' : count}
          </span>
        ) : null}
      </button>
      {open ? (
        <>
          <button type="button" className="fixed inset-0 z-40" aria-label="Close notifications" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-50 mt-2 w-80 rounded-2xl border border-line bg-[var(--brand-surface)] p-3 shadow-card">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-sm font-medium">Notifications</p>
              <button
                type="button"
                className="text-xs text-[var(--brand-primary)]"
                onClick={() => markAll.mutate()}
              >
                Mark all read
              </button>
            </div>
            <ul className="max-h-80 space-y-2 overflow-y-auto">
              {(notifications.data ?? []).slice(0, 20).map((item) => (
                <li key={item.id}>
                  <Link
                    to={item.link_path || '/expenses'}
                    className={cn(
                      'block rounded-xl px-3 py-2 text-sm hover:bg-cream',
                      !item.is_read && 'bg-cream/70',
                    )}
                    onClick={() => {
                      if (!item.is_read) markRead.mutate(item.id)
                      setOpen(false)
                    }}
                  >
                    <p className="font-medium">{item.title}</p>
                    {item.body ? <p className="mt-0.5 text-xs text-ink-soft">{item.body}</p> : null}
                    <p className="mt-1 text-[11px] text-ink-soft">{formatWhen(item.created_at)}</p>
                  </Link>
                </li>
              ))}
              {(notifications.data ?? []).length === 0 ? (
                <li className="px-2 py-4 text-sm text-ink-soft">No notifications yet.</li>
              ) : null}
            </ul>
          </div>
        </>
      ) : null}
    </div>
  )
}

function useDesktopNav() {
  const [desktop, setDesktop] = useState(() => window.matchMedia('(min-width: 1024px)').matches)

  useEffect(() => {
    const media = window.matchMedia('(min-width: 1024px)')
    const onChange = () => setDesktop(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  return desktop
}

function WorkspaceBody({
  isLoading,
  isError,
  error,
  onRetry,
  hasOrganization,
}: {
  isLoading: boolean
  isError: boolean
  error: unknown
  onRetry: () => void
  hasOrganization: boolean
}) {
  if (!hasOrganization && isLoading) return <PageSkeleton />
  if (!hasOrganization) {
    return (
      <section className="rounded-3xl border border-line bg-[var(--brand-surface)] p-6">
        <h1 className="font-display text-3xl">No organization yet</h1>
        <p className="mt-2 text-ink-soft">Accept an invitation to join a business, or ask a platform administrator to create one.</p>
      </section>
    )
  }
  if (isLoading) return <PageSkeleton />
  if (isError) return <ErrorState error={error} onRetry={onRetry} />
  return <Outlet />
}
