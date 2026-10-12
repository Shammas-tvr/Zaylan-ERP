import { useMe, usePlans } from '../workspace/queries.ts'
import { featureLabel, labelOf } from '../../shared/labels.ts'
import { canPlatform } from '../../shared/permissions.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { ErrorState, NoAccess, PageSkeleton } from '../../shared/ui/Feedback.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'

export function PlansPage() {
  usePageTitle('Plans')
  const me = useMe()
  const plans = usePlans()
  if (me.isLoading || plans.isLoading) return <PageSkeleton />
  if (!canPlatform(me.data?.platform_permissions, 'platform.plans.view')) {
    return <NoAccess>Plan management is limited to platform administrators.</NoAccess>
  }
  if (plans.isError) return <ErrorState error={plans.error} onRetry={() => void plans.refetch()} />

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Plans"
        description="Feature access and limits live on the plan. Payment collection can be connected later without changing these screens."
      />
      <div className="grid gap-4 lg:grid-cols-3">
        {(plans.data ?? []).map((plan) => (
          <Panel key={plan.id} className="flex flex-col">
            <div className="flex items-start justify-between gap-3">
              <h2 className="font-display text-3xl">{plan.name}</h2>
              <StatusBadge status={plan.is_active ? 'active' : 'inactive'} />
            </div>
            <p className="mt-2 text-sm text-ink-soft">{plan.description}</p>
            <dl className="mt-5 grid gap-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-ink-soft">Trial</dt>
                <dd>{plan.trial_days} days</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-ink-soft">Branches</dt>
                <dd>{plan.max_branches ?? 'Unlimited'}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-ink-soft">People</dt>
                <dd>{plan.max_members ?? 'Unlimited'}</dd>
              </div>
            </dl>
            <ul className="mt-5 grid gap-2 text-sm">
              {plan.features.map((feature) => (
                <li key={feature}>{labelOf(featureLabel, feature)}</li>
              ))}
            </ul>
          </Panel>
        ))}
      </div>
    </div>
  )
}
