import { Link } from 'react-router-dom'
import { useAudit, useMembers, useWorkspace } from '../workspace/queries.ts'
import { actionLabel, featureLabel, formatDate, formatWhen, industryLabel, labelOf } from '../../shared/labels.ts'
import { can } from '../../shared/permissions.ts'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'

export function OverviewPage() {
  const workspace = useWorkspace()
  const context = workspace.data
  const allowMembers = can(context?.permissions, 'members.view')
  const allowAudit = can(context?.permissions, 'audit.view')
  const allowPlan = can(context?.permissions, 'subscription.view')
  const members = useMembers(allowMembers)
  const audit = useAudit('', allowAudit)

  if (!context) return null
  const { organization, subscription, branches } = context
  const selected = branches.filter((branch) => branch.status === 'active')

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <PageHeader
          title={organization.name}
          description={`${labelOf(industryLabel, organization.industry)} · ${organization.currency} · ${organization.timezone}`}
        />
        <StatusBadge status={organization.status} />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Fact label="Branches" value={String(selected.length)} detail={allowPlan ? limitDetail(selected.length, subscription.max_branches) : 'You can work in assigned branches'} />
        {allowMembers ? (
          <Fact label="People" value={String(members.data?.length ?? '—')} detail={allowPlan ? limitDetail(members.data?.length ?? 0, subscription.max_members) : 'Active members'} />
        ) : (
          <Fact label="Your access" value="Branch" detail={selected.map((branch) => branch.name).join(', ') || 'No branch assigned'} />
        )}
        {allowPlan ? (
          <Fact label="Plan" value={subscription.plan_name} detail={subscription.trial_ends_at ? `Trial ends ${formatDate(subscription.trial_ends_at, organization.timezone)}` : labelOf({ active: 'Subscription active' }, subscription.status ?? '')} />
        ) : (
          <Fact label="Sales totals" value="Hidden" detail="Organization totals stay on authorized reports." />
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
        <Panel>
          <div className="mb-4 flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Branches</h2>
            {can(context.permissions, 'branches.view') ? (
              <Link to="/branches" className="text-sm font-medium text-[var(--brand-primary)]">
                View all
              </Link>
            ) : null}
          </div>
          <ul className="divide-y divide-line">
            {branches.map((branch) => (
              <li key={branch.id} className="flex items-center justify-between gap-3 py-3">
                <div>
                  <p className="font-medium">{branch.name}</p>
                  <p className="text-sm text-ink-soft">{branch.code} · {branch.address || 'Address not set'}</p>
                </div>
                <StatusBadge status={branch.status} />
              </li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <h2 className="text-lg font-semibold">Included in the plan</h2>
          {allowPlan ? (
            <ul className="mt-4 grid gap-2 text-sm">
              {subscription.features.map((feature) => (
                <li key={feature} className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-[var(--brand-secondary)]" />
                  {labelOf(featureLabel, feature)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-sm text-ink-soft">
              Point of sale opens in a later release. You will see your own shift there, not organization-wide totals.
            </p>
          )}
        </Panel>
      </div>

      {allowAudit ? (
        <Panel>
          <h2 className="text-lg font-semibold">Recent activity</h2>
          <ul className="mt-3 divide-y divide-line">
            {(audit.data ?? []).slice(0, 5).map((event) => (
              <li key={event.id} className="grid gap-1 py-3 sm:grid-cols-[180px_1fr]">
                <p className="text-sm text-ink-soft">{formatWhen(event.created_at, organization.timezone)}</p>
                <p>
                  <span className="font-medium">{labelOf(actionLabel, event.action)}</span>
                  <span className="text-ink-soft"> · {event.summary}</span>
                </p>
              </li>
            ))}
          </ul>
        </Panel>
      ) : null}
    </div>
  )
}

function Fact({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Panel className="p-5">
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="mt-2 font-display text-3xl tracking-tight">{value}</p>
      <p className="mt-2 text-sm text-ink-soft">{detail}</p>
    </Panel>
  )
}

function limitDetail(used: number, limit: number | null) {
  if (limit === null) return `${used} in use · no plan limit`
  return `${used} of ${limit} used`
}
