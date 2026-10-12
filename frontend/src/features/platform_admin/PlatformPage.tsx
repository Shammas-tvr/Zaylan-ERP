import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { platformApi } from '../../shared/api/client'
import { queryKeys } from '../../shared/api/queryClient'
import { ApiError } from '../../shared/api/axios'
import { Alert, Button, Card, Field, Form, Page, StatusPill } from '../../shared/components/ui'

export function PlatformPage() {
  const queryClient = useQueryClient()
  const [inviteUrl, setInviteUrl] = useState('')
  const [error, setError] = useState('')
  const tenants = useQuery({ queryKey: queryKeys.platformTenants, queryFn: platformApi.tenants })
  const plans = useQuery({ queryKey: queryKeys.platformPlans, queryFn: platformApi.plans })
  const metrics = useQuery({ queryKey: queryKeys.platformMetrics, queryFn: platformApi.metrics })
  const onboard = useMutation({
    mutationFn: platformApi.onboard,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.platformTenants }),
  })

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setError('')
    try {
      const result = await onboard.mutateAsync({
        name: String(data.get('name')),
        slug: String(data.get('slug')),
        industry: String(data.get('industry')),
        plan_code: String(data.get('plan_code')),
        owner_email: String(data.get('owner_email')),
      })
      setInviteUrl(result.owner_invitation_url)
      event.currentTarget.reset()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to onboard this tenant.')
    }
  }

  return (
    <Page
      title="Platform administration"
      subtitle="Lifecycle, plans and operational counts. This area never shows a tenant's sales or expenses."
    >
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <p className="text-xs uppercase tracking-wide text-tan">Tenants</p>
          <p className="mt-2 text-3xl font-semibold">{tenants.data?.count ?? '—'}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-wide text-tan">Active members</p>
          <p className="mt-2 text-3xl font-semibold">{metrics.data?.total_active_members ?? '—'}</p>
        </Card>
        <Card>
          <p className="text-xs uppercase tracking-wide text-tan">Branches</p>
          <p className="mt-2 text-3xl font-semibold">{metrics.data?.total_branches ?? '—'}</p>
        </Card>
      </div>
      <Card>
        <h2 className="mb-3 font-display text-lg font-semibold">Onboard a tenant</h2>
        <Form onSubmit={onSubmit}>
          {error ? <Alert>{error}</Alert> : null}
          {inviteUrl ? <Alert tone="success">Owner invitation (shown once): {inviteUrl}</Alert> : null}
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Business name" name="name" required />
            <Field label="Slug" name="slug" required />
            <Field label="Owner email" name="owner_email" type="email" required />
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-semibold">Industry</span>
              <select name="industry" className="rounded-lg border border-line bg-surface px-3 py-2" defaultValue="DESSERT_SHOP">
                <option value="DESSERT_SHOP">Dessert shop</option>
                <option value="BAKERY">Bakery</option>
                <option value="CAFE">Cafe</option>
                <option value="RESTAURANT">Restaurant</option>
                <option value="RETAIL">Retail</option>
                <option value="OTHER">Other</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-semibold">Plan</span>
              <select name="plan_code" className="rounded-lg border border-line bg-surface px-3 py-2">
                {(plans.data || []).map((plan) => (
                  <option key={plan.code} value={plan.code}>{plan.name}</option>
                ))}
              </select>
            </label>
          </div>
          <Button type="submit" disabled={onboard.isPending}>Create tenant</Button>
        </Form>
      </Card>
      <Card>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-line text-ink/60">
              <th className="py-2 font-medium">Tenant</th>
              <th className="py-2 font-medium">Plan</th>
              <th className="py-2 font-medium">Status</th>
              <th className="py-2 font-medium">Onboarding</th>
            </tr>
          </thead>
          <tbody>
            {(tenants.data?.results || []).map((tenant) => (
              <tr key={tenant.id} className="border-b border-line/70">
                <td className="py-2 font-semibold">{tenant.name}</td>
                <td className="py-2">{tenant.subscription?.plan_name || '—'}</td>
                <td className="py-2"><StatusPill value={tenant.status} /></td>
                <td className="py-2"><StatusPill value={tenant.onboarding_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </Page>
  )
}
