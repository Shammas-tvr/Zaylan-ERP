import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  useMe,
  usePlans,
  useSetTenantStatus,
  useTenant,
  useUpdateBrand,
} from '../workspace/queries.ts'
import type { BrandUpdateInput } from '../../shared/api/workspace.ts'
import type { OrgStatus } from '../../shared/api/types.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { industryLabel, labelOf } from '../../shared/labels.ts'
import { canPlatform } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { SelectField, TextField } from '../../shared/ui/Field.tsx'
import { ErrorState, NoAccess, PageSkeleton } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'

function sanitizeSlug(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 63)
}

export function BrandDetailPage() {
  const { brandId = '' } = useParams()
  const me = useMe()
  const brand = useTenant(brandId)
  const plans = usePlans()
  const save = useUpdateBrand()
  const setStatus = useSetTenantStatus()
  const [form, setForm] = useState<BrandUpdateInput | null>(null)
  const [editing, setEditing] = useState(false)
  const [confirm, setConfirm] = useState<{ status: OrgStatus; label: string } | null>(null)

  usePageTitle(brand.data?.name ?? 'Brand')

  useEffect(() => {
    if (!brand.data) return
    setForm({
      name: brand.data.name,
      slug: brand.data.slug,
      industry: brand.data.industry,
      legal_name: brand.data.legal_name,
      contact_phone: brand.data.contact_phone,
      owner_email: brand.data.contact_email,
      plan_code: brand.data.plan_code,
    })
  }, [brand.data])

  const allowed = canPlatform(me.data?.platform_permissions, 'platform.tenants.view')
  const canManage = canPlatform(me.data?.platform_permissions, 'platform.tenants.manage')

  if (me.isLoading || brand.isLoading) return <PageSkeleton />
  if (!allowed) return <NoAccess>Platform administration is separate from customer records.</NoAccess>
  if (brand.isError) return <ErrorState error={brand.error} onRetry={() => void brand.refetch()} />
  if (!brand.data || !form) return null

  const row = brand.data
  const locked = !editing
  const statusAction: { status: OrgStatus; label: string } | null =
    row.status === 'active'
      ? { status: 'suspended', label: 'Suspend' }
      : { status: 'active', label: 'Activate' }

  return (
    <div className="grid gap-6">
      <PageHeader
        title={row.name}
        description="Brand profile, portal, and access."
        action={
          <Link to="/platform/brands" className="text-sm text-ink-soft underline-offset-2 hover:underline">
            Back to brands
          </Link>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge status={row.status} />
        <span className="text-sm text-ink-soft">
          {row.branch_count} branches · {row.member_count} people
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.8fr)]">
        <Panel>
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-display text-2xl tracking-tight">Details</h2>
            {canManage && !editing ? (
              <Button variant="secondary" onClick={() => setEditing(true)}>
                Edit
              </Button>
            ) : null}
          </div>
          <form
            className="mt-5 grid gap-4 sm:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault()
              save.mutate(
                { id: row.id, input: form },
                { onSuccess: () => setEditing(false) },
              )
            }}
          >
            <TextField
              label="Brand name"
              required
              disabled={locked}
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
            <TextField
              label="Legal / company name"
              disabled={locked}
              value={form.legal_name}
              onChange={(event) => setForm({ ...form, legal_name: event.target.value })}
            />
            <TextField
              label="Slug"
              required
              minLength={3}
              disabled={locked}
              value={form.slug}
              onChange={(event) => setForm({ ...form, slug: sanitizeSlug(event.target.value) })}
              hint={editing ? 'Must stay unique. Portal URL updates with the slug.' : undefined}
            />
            <SelectField
              label="Industry"
              disabled={locked}
              value={form.industry}
              onChange={(event) => setForm({ ...form, industry: event.target.value })}
            >
              {Object.entries(industryLabel).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </SelectField>
            <TextField
              label="Contact phone"
              disabled={locked}
              value={form.contact_phone}
              onChange={(event) => setForm({ ...form, contact_phone: event.target.value })}
            />
            <SelectField
              label="Plan"
              disabled={locked}
              value={form.plan_code}
              onChange={(event) => setForm({ ...form, plan_code: event.target.value })}
            >
              {(plans.data ?? []).map((plan) => (
                <option key={plan.code} value={plan.code}>
                  {plan.name}
                </option>
              ))}
            </SelectField>
            <div className="sm:col-span-2">
              <TextField
                label="Brand Admin email"
                type="email"
                required
                disabled={locked}
                value={form.owner_email}
                onChange={(event) => setForm({ ...form, owner_email: event.target.value })}
                hint={editing ? 'Must be unique. This is the email used to sign in.' : undefined}
              />
            </div>
            {save.isError ? <p className="text-sm text-danger sm:col-span-2">{errorMessage(save.error)}</p> : null}
            {editing ? (
              <div className="flex gap-2 sm:col-span-2">
                <Button type="submit" disabled={save.isPending}>
                  {save.isPending ? 'Saving…' : 'Save changes'}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setEditing(false)
                    setForm({
                      name: row.name,
                      slug: row.slug,
                      industry: row.industry,
                      legal_name: row.legal_name,
                      contact_phone: row.contact_phone,
                      owner_email: row.contact_email,
                      plan_code: row.plan_code,
                    })
                  }}
                >
                  Cancel
                </Button>
              </div>
            ) : null}
          </form>
        </Panel>

        <div className="grid gap-6">
          <Panel>
            <h2 className="font-display text-2xl tracking-tight">Portal</h2>
            <p className="mt-3 break-all text-sm">
              {row.portal_url ? (
                <a className="underline" href={row.portal_url} target="_blank" rel="noreferrer">
                  {row.portal_url}
                </a>
              ) : (
                '—'
              )}
            </p>
            <p className="mt-2 text-sm text-ink-soft">Industry: {labelOf(industryLabel, row.industry)}</p>
            {row.portal_url ? (
              <Button
                className="mt-4"
                variant="secondary"
                onClick={() => void navigator.clipboard.writeText(row.portal_url)}
              >
                Copy portal URL
              </Button>
            ) : null}
          </Panel>

          {canManage && statusAction ? (
            <Panel>
              <h2 className="font-display text-2xl tracking-tight">Access</h2>
              <p className="mt-3 text-sm text-ink-soft">
                {row.status === 'active'
                  ? 'Suspend pauses sign-in for this brand. Activate restores it.'
                  : 'Activate lets people in this brand sign in again.'}
              </p>
              <Button
                className="mt-4"
                variant={statusAction.status === 'active' ? 'primary' : 'danger'}
                onClick={() => setConfirm(statusAction)}
              >
                {statusAction.label}
              </Button>
            </Panel>
          ) : null}
        </div>
      </div>

      <Modal
        open={Boolean(confirm)}
        title={confirm ? `${confirm.label} ${row.name}` : ''}
        onClose={() => setConfirm(null)}
      >
        <p className="text-ink-soft">
          {confirm?.status === 'suspended'
            ? 'People in this brand cannot open it until you activate it again.'
            : 'This brand will be able to sign in again.'}
        </p>
        {setStatus.isError ? <p className="mt-3 text-sm text-danger">{errorMessage(setStatus.error)}</p> : null}
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setConfirm(null)}>
            Cancel
          </Button>
          <Button
            variant={confirm?.status === 'active' ? 'primary' : 'danger'}
            disabled={setStatus.isPending}
            onClick={() => {
              if (!confirm) return
              setStatus.mutate(
                { id: row.id, status: confirm.status },
                {
                  onSuccess: () => {
                    setConfirm(null)
                    void brand.refetch()
                  },
                },
              )
            }}
          >
            {confirm?.label}
          </Button>
        </div>
      </Modal>
    </div>
  )
}
