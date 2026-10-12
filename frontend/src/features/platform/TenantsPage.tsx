import { useState } from 'react'
import {
  useCreateBrand,
  useMe,
  usePlans,
  usePlatformMetrics,
  useSetTenantStatus,
  useSetTenantSubscription,
  useTenants,
} from '../workspace/queries.ts'
import type { BrandOnboardInput, OrgStatus, PlatformTenant } from '../../shared/api/types.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { industryLabel, labelOf } from '../../shared/labels.ts'
import { canPlatform } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { SelectField, TextField } from '../../shared/ui/Field.tsx'
import { ErrorState, NoAccess, PageSkeleton } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'

const transitions: Record<OrgStatus, Array<{ status: OrgStatus; label: string }>> = {
  pending: [
    { status: 'active', label: 'Activate' },
    { status: 'deactivated', label: 'Deactivate' },
  ],
  active: [
    { status: 'suspended', label: 'Suspend' },
    { status: 'deactivated', label: 'Deactivate' },
  ],
  suspended: [
    { status: 'active', label: 'Activate' },
    { status: 'deactivated', label: 'Deactivate' },
  ],
  deactivated: [{ status: 'active', label: 'Activate' }],
}

const emptyForm: BrandOnboardInput = {
  name: '',
  slug: '',
  industry: 'other',
  plan_code: 'growth',
  owner_email: '',
  legal_name: '',
  contact_email: '',
  contact_phone: '',
}

export function TenantsPage() {
  usePageTitle('Brands')
  const me = useMe()
  const tenants = useTenants()
  const metrics = usePlatformMetrics()
  const plans = usePlans()
  const update = useSetTenantStatus()
  const createBrand = useCreateBrand()
  const setSubscription = useSetTenantSubscription()
  const [pending, setPending] = useState<{ tenant: PlatformTenant; status: OrgStatus; label: string } | null>(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState<BrandOnboardInput>(emptyForm)
  const [inviteResult, setInviteResult] = useState<{ url: string; emailSent: boolean; name: string } | null>(null)
  const [detail, setDetail] = useState<PlatformTenant | null>(null)
  const [planCode, setPlanCode] = useState('')

  const allowed = canPlatform(me.data?.platform_permissions, 'platform.tenants.view')
  const canManage = canPlatform(me.data?.platform_permissions, 'platform.tenants.manage')
  const canMetrics = canPlatform(me.data?.platform_permissions, 'platform.metrics.view')

  if (me.isLoading || tenants.isLoading) return <PageSkeleton />
  if (!allowed) return <NoAccess>Platform administration is separate from customer records.</NoAccess>
  if (tenants.isError) return <ErrorState error={tenants.error} onRetry={() => void tenants.refetch()} />

  const rows = tenants.data ?? []
  const m = metrics.data

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Brands"
        description="Create customer brands, invite Brand Admins, and manage subscriptions. Platform admins do not see brand expense details here."
        action={
          canManage ? (
            <Button
              onClick={() => {
                setForm({
                  ...emptyForm,
                  plan_code: plans.data?.[0]?.code ?? 'growth',
                })
                setCreating(true)
              }}
            >
              Create brand
            </Button>
          ) : null
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Brands" value={String(canMetrics && m ? m.total_brands : rows.length)} />
        <Metric
          label="Active brands"
          value={String(
            canMetrics && m
              ? m.tenants_by_status?.ACTIVE ?? rows.filter((t) => t.status === 'active').length
              : rows.filter((t) => t.status === 'active').length,
          )}
        />
        <Metric label="Branches" value={String(canMetrics && m ? m.total_branches : rows.reduce((s, t) => s + t.branch_count, 0))} />
        <Metric
          label="Active subscriptions"
          value={String(canMetrics && m ? m.active_subscriptions : rows.filter((t) => t.status === 'active').length)}
        />
      </div>
      <Panel>
        <DataTable
          caption="Brands"
          rows={rows}
          rowKey={(tenant) => tenant.id}
          empty="No brands yet."
          columns={[
            {
              header: 'Brand',
              render: (tenant) => (
                <button type="button" className="text-left font-medium underline-offset-2 hover:underline" onClick={() => {
                  setDetail(tenant)
                  setPlanCode(tenant.plan_code)
                }}>
                  {tenant.name}
                </button>
              ),
            },
            { header: 'Industry', render: (tenant) => labelOf(industryLabel, tenant.industry) },
            { header: 'Plan', render: (tenant) => tenant.plan_name },
            { header: 'Branches', render: (tenant) => String(tenant.branch_count) },
            { header: 'Status', render: (tenant) => <StatusBadge status={tenant.status} /> },
            {
              header: 'Action',
              render: (tenant) =>
                canManage ? (
                  <div className="flex flex-wrap gap-2">
                    {transitions[tenant.status].map((action) => (
                      <Button key={action.status} size="sm" variant="secondary" onClick={() => setPending({ tenant, ...action })}>
                        {action.label}
                      </Button>
                    ))}
                  </div>
                ) : (
                  '—'
                ),
            },
          ]}
        />
      </Panel>

      <Modal open={creating} title="Create brand" onClose={() => setCreating(false)}>
        <form
          className="grid gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            createBrand.mutate(form, {
              onSuccess: (result) => {
                setCreating(false)
                setInviteResult({
                  url: result.owner_invitation_url,
                  emailSent: result.invitation_email_sent,
                  name: result.tenant.name,
                })
              },
            })
          }}
        >
          <TextField label="Brand name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value, slug: form.slug || slugify(e.target.value) })} />
          <TextField label="Slug" required value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} />
          <TextField label="Legal / company name" value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} />
          <SelectField label="Industry" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })}>
            {Object.entries(industryLabel).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </SelectField>
          <SelectField label="Plan" value={form.plan_code} onChange={(e) => setForm({ ...form, plan_code: e.target.value })}>
            {(plans.data ?? []).map((plan) => (
              <option key={plan.code} value={plan.code}>
                {plan.name}
              </option>
            ))}
          </SelectField>
          <TextField label="Brand Admin email" type="email" required value={form.owner_email} onChange={(e) => setForm({ ...form, owner_email: e.target.value })} />
          <TextField label="Primary notification email" type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} hint="Defaults to the Brand Admin email if left blank." />
          <TextField label="Contact phone" value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} />
          {createBrand.isError ? <p className="text-sm text-danger">{errorMessage(createBrand.error)}</p> : null}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createBrand.isPending}>
              Create & invite
            </Button>
          </div>
        </form>
      </Modal>

      <Modal open={Boolean(inviteResult)} title="Brand Admin invitation" onClose={() => setInviteResult(null)}>
        <p className="text-ink-soft">
          {inviteResult?.name} is ready. {inviteResult?.emailSent ? 'An invitation email was sent.' : 'Email could not be delivered; copy the link below.'}
        </p>
        <TextField label="Invitation link" readOnly value={inviteResult?.url ?? ''} />
        <div className="mt-4 flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              void navigator.clipboard.writeText(inviteResult?.url ?? '')
            }}
          >
            Copy link
          </Button>
          <Button onClick={() => setInviteResult(null)}>Done</Button>
        </div>
      </Modal>

      <Modal open={Boolean(pending)} title={pending ? `${pending.label} ${pending.tenant.name}` : ''} onClose={() => setPending(null)}>
        <p className="text-ink-soft">
          {pending?.status === 'suspended'
            ? 'People in this brand will be unable to open it until it is activated again.'
            : 'This change is written to the platform audit log.'}
        </p>
        {update.isError ? <p className="mt-3 text-sm text-danger">{errorMessage(update.error)}</p> : null}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setPending(null)}>
            Cancel
          </Button>
          <Button
            variant={pending?.status === 'active' ? 'primary' : 'danger'}
            disabled={update.isPending}
            onClick={() => {
              if (!pending) return
              update.mutate({ id: pending.tenant.id, status: pending.status }, { onSuccess: () => setPending(null) })
            }}
          >
            {pending?.label}
          </Button>
        </div>
      </Modal>

      <Modal open={Boolean(detail)} title={detail?.name ?? 'Brand'} onClose={() => setDetail(null)}>
        {detail ? (
          <div className="grid gap-3 text-sm">
            <p>
              <span className="text-ink-soft">Legal name:</span> {detail.legal_name || '—'}
            </p>
            <p>
              <span className="text-ink-soft">Notification email:</span> {detail.contact_email || '—'}
            </p>
            <p>
              <span className="text-ink-soft">Subscription:</span> {detail.plan_name} ({detail.subscription_status || '—'})
            </p>
            <p>
              <span className="text-ink-soft">Branches / members:</span> {detail.branch_count} / {detail.member_count}
            </p>
            {canManage ? (
              <form
                className="mt-2 grid gap-3"
                onSubmit={(event) => {
                  event.preventDefault()
                  setSubscription.mutate(
                    { id: detail.id, plan_code: planCode },
                    { onSuccess: () => setDetail(null) },
                  )
                }}
              >
                <SelectField label="Change plan" value={planCode} onChange={(e) => setPlanCode(e.target.value)}>
                  {(plans.data ?? []).map((plan) => (
                    <option key={plan.code} value={plan.code}>
                      {plan.name}
                    </option>
                  ))}
                </SelectField>
                {setSubscription.isError ? <p className="text-danger">{errorMessage(setSubscription.error)}</p> : null}
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="secondary" onClick={() => setDetail(null)}>
                    Close
                  </Button>
                  <Button type="submit" disabled={setSubscription.isPending}>
                    Save plan
                  </Button>
                </div>
              </form>
            ) : (
              <div className="mt-3 flex justify-end">
                <Button onClick={() => setDetail(null)}>Close</Button>
              </div>
            )}
          </div>
        ) : null}
      </Modal>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Panel className="p-5">
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="mt-2 font-display text-3xl">{value}</p>
    </Panel>
  )
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 63)
}
