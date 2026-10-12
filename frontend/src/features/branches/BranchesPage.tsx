import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { tenantApi } from '../../shared/api/client'
import { queryKeys } from '../../shared/api/queryClient'
import { ApiError } from '../../shared/api/axios'
import { Alert, Button, Card, Field, Form, Page, StatusPill } from '../../shared/components/ui'
import { can, useTenant } from '../tenant_switcher/TenantProvider'
import { useAuth } from '../authentication/AuthProvider'

export function BranchesPage() {
  const tenant = useTenant()
  const { organizationId } = useAuth()
  const queryClient = useQueryClient()
  const [error, setError] = useState('')
  const query = useQuery({
    queryKey: queryKeys.branches(organizationId!),
    queryFn: tenantApi.branches,
  })
  const create = useMutation({
    mutationFn: tenantApi.createBranch,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.branches(organizationId!) }),
  })

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setError('')
    try {
      await create.mutateAsync({ code: String(data.get('code')), name: String(data.get('name')) })
      event.currentTarget.reset()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to create the branch.')
    }
  }

  return (
    <Page title="Branches" subtitle="Each branch stays inside this organization. Other tenants cannot see these records.">
      {can(tenant, 'branches.manage') ? (
        <Card>
          <h2 className="mb-3 font-display text-lg font-semibold">Add a branch</h2>
          <Form onSubmit={onSubmit}>
            {error ? <Alert>{error}</Alert> : null}
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Code" name="code" required maxLength={16} />
              <Field label="Name" name="name" required />
            </div>
            <Button type="submit" disabled={create.isPending}>Create branch</Button>
          </Form>
        </Card>
      ) : null}
      <Card>
        {query.isLoading ? <p>Loading…</p> : null}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line text-ink/60">
                <th className="py-2 font-medium">Code</th>
                <th className="py-2 font-medium">Name</th>
                <th className="py-2 font-medium">City</th>
                <th className="py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {(query.data?.results || []).map((branch) => (
                <tr key={branch.id} className="border-b border-line/70">
                  <td className="py-2 font-semibold">{branch.code}</td>
                  <td className="py-2">{branch.name}</td>
                  <td className="py-2">{branch.city || '—'}</td>
                  <td className="py-2"><StatusPill value={branch.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </Page>
  )
}
