import { can, useTenant } from '../tenant_switcher/TenantProvider'
import { Card, Page, StatusPill } from '../../shared/components/ui'

export function DashboardPage() {
  const tenant = useTenant()
  return (
    <Page
      title={tenant.organization.name}
      subtitle="Organization overview. Sales totals and profitability reports arrive in later phases."
    >
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <p className="text-xs uppercase tracking-wide text-tan">Status</p>
          <div className="mt-2"><StatusPill value={tenant.organization.status} /></div>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-wide text-tan">Branches you can access</p>
          <p className="mt-2 text-3xl font-semibold">{tenant.branches.length}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-wide text-tan">Currency</p>
          <p className="mt-2 text-3xl font-semibold">{tenant.organization.currency}</p>
        </Card>
      </div>
      <Card>
        <h2 className="font-display text-xl font-semibold">Your access</h2>
        <p className="mt-1 text-sm text-ink/70">
          {can(tenant, 'organization.manage')
            ? 'You can manage this organization.'
            : 'You have limited operational access. Sensitive totals will stay hidden unless you are granted the matching permission.'}
        </p>
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {tenant.branches.map((branch) => (
            <li key={branch.id} className="rounded-lg border border-line bg-cream px-3 py-2 text-sm">
              <strong>{branch.name}</strong>
              <span className="ml-2 text-ink/60">{branch.code}</span>
            </li>
          ))}
        </ul>
      </Card>
    </Page>
  )
}
