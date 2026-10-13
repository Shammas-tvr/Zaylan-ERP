import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useCreateBrand,
  useMe,
  usePlans,
  usePlatformMetrics,
  useTenants,
} from '../workspace/queries.ts'
import type { BrandOnboardInput } from '../../shared/api/types.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { industryLabel } from '../../shared/labels.ts'
import { canPlatform } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { PasswordField, SelectField, TextField } from '../../shared/ui/Field.tsx'
import { ErrorState, NoAccess, PageSkeleton } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'

const emptyForm: BrandOnboardInput = {
  name: '',
  slug: '',
  industry: 'other',
  plan_code: 'growth',
  owner_email: '',
  owner_password: '',
  owner_full_name: '',
  legal_name: '',
  contact_phone: '',
}

/** Auto slug: first + last word (Bariq Mens Fashions → bariq-fashions). */
function shortSlugFromName(name: string) {
  const words = name
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean)
  if (words.length === 0) return ''
  let slug = words.length === 1 ? words[0] : `${words[0]}-${words[words.length - 1]}`
  if (slug.length < 3) slug = (slug + '-brand').slice(0, 63)
  return slug.slice(0, 63)
}

/** Manual slug field: allow dashes and alphanumerics only. */
function sanitizeSlug(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 63)
}

export function TenantsPage() {
  usePageTitle('Brands')
  const navigate = useNavigate()
  const me = useMe()
  const tenants = useTenants()
  const metrics = usePlatformMetrics()
  const plans = usePlans()
  const createBrand = useCreateBrand()
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState<BrandOnboardInput>(emptyForm)
  const [slugManual, setSlugManual] = useState(false)
  const [createdNotice, setCreatedNotice] = useState<{ name: string; email: string; portalUrl: string } | null>(null)

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
        description="Create brands and Brand Admin accounts. Platform admins do not see brand expense details here."
        action={
          canManage ? (
            <Button
              onClick={() => {
                setSlugManual(false)
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
          onRowClick={(tenant) => navigate(`/platform/brands/${tenant.id}`)}
          columns={[
            { header: 'Brand', render: (tenant) => <span className="font-medium">{tenant.name}</span> },
            { header: 'Slug', render: (tenant) => tenant.slug },
            { header: 'Plan', render: (tenant) => tenant.plan_name },
            { header: 'Branches', render: (tenant) => String(tenant.branch_count) },
            { header: 'Status', render: (tenant) => <StatusBadge status={tenant.status} /> },
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
                setCreatedNotice({
                  name: result.tenant.name,
                  email: result.brand_admin_email,
                  portalUrl: result.portal_url,
                })
              },
            })
          }}
        >
          <TextField
            label="Brand name"
            required
            value={form.name}
            onChange={(e) => {
              const name = e.target.value
              setForm((prev) => ({
                ...prev,
                name,
                slug: slugManual ? prev.slug : shortSlugFromName(name),
              }))
            }}
          />
          <TextField
            label="Slug"
            required
            minLength={3}
            value={form.slug}
            onChange={(e) => {
              setSlugManual(true)
              setForm({ ...form, slug: sanitizeSlug(e.target.value) })
            }}
            hint={
              form.slug
                ? `Portal URL: ${typeof window !== 'undefined' ? window.location.origin : ''}/b/${form.slug}`
                : 'Short code from the brand name. Editable; must be unique.'
            }
          />
          <TextField
            label="Legal / company name"
            value={form.legal_name}
            onChange={(e) => setForm({ ...form, legal_name: e.target.value })}
          />
          <SelectField
            label="Industry"
            value={form.industry}
            onChange={(e) => setForm({ ...form, industry: e.target.value })}
          >
            {Object.entries(industryLabel).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Plan"
            value={form.plan_code}
            onChange={(e) => setForm({ ...form, plan_code: e.target.value })}
          >
            {(plans.data ?? []).map((plan) => (
              <option key={plan.code} value={plan.code}>
                {plan.name}
              </option>
            ))}
          </SelectField>
          <TextField
            label="Brand Admin name"
            value={form.owner_full_name}
            onChange={(e) => setForm({ ...form, owner_full_name: e.target.value })}
          />
          <TextField
            label="Brand Admin email"
            type="email"
            required
            value={form.owner_email}
            onChange={(e) => setForm({ ...form, owner_email: e.target.value })}
            hint="Must be unique. Used to sign in at /login."
          />
          <PasswordField
            label="Brand Admin password"
            required
            value={form.owner_password}
            onChange={(e) => setForm({ ...form, owner_password: e.target.value })}
          />
          <TextField
            label="Contact phone"
            value={form.contact_phone}
            onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
          />
          {createBrand.isError ? <p className="text-sm text-danger">{errorMessage(createBrand.error)}</p> : null}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createBrand.isPending}>
              Create brand
            </Button>
          </div>
        </form>
      </Modal>

      <Modal open={Boolean(createdNotice)} title="Brand created" onClose={() => setCreatedNotice(null)}>
        <p className="text-ink-soft">
          {createdNotice?.name} is ready. Share the Brand Admin email and password you set. Brand users sign in at{' '}
          <strong>/login</strong>.
        </p>
        <div className="mt-4 grid gap-3">
          <TextField label="Brand Admin email" readOnly value={createdNotice?.email ?? ''} />
          <TextField label="Brand portal URL" readOnly value={createdNotice?.portalUrl ?? ''} />
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => void navigator.clipboard.writeText(createdNotice?.portalUrl ?? '')}
          >
            Copy portal URL
          </Button>
          <Button onClick={() => setCreatedNotice(null)}>Done</Button>
        </div>
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
