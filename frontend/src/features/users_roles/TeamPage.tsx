import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { tenantApi } from '../../shared/api/client'
import { queryKeys } from '../../shared/api/queryClient'
import { ApiError } from '../../shared/api/axios'
import { Alert, Button, Card, Field, Form, Page, StatusPill } from '../../shared/components/ui'
import { can, useTenant } from '../tenant_switcher/TenantProvider'
import { useAuth } from '../authentication/AuthProvider'

export function TeamPage() {
  const tenant = useTenant()
  const { organizationId } = useAuth()
  const queryClient = useQueryClient()
  const [inviteUrl, setInviteUrl] = useState('')
  const [error, setError] = useState('')
  const members = useQuery({ queryKey: queryKeys.members(organizationId!), queryFn: tenantApi.members })
  const roles = useQuery({ queryKey: queryKeys.roles(organizationId!), queryFn: tenantApi.roles, enabled: can(tenant, 'roles.view') })
  const invite = useMutation({
    mutationFn: tenantApi.invite,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.invitations(organizationId!) }),
  })

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setError('')
    try {
      const result = await invite.mutateAsync({
        email: String(data.get('email')),
        assignments: [{ role_id: String(data.get('role_id')), scope: String(data.get('scope')) }],
        branch_ids: [],
      })
      setInviteUrl(result.invitation_url)
      event.currentTarget.reset()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Unable to send the invitation.')
    }
  }

  return (
    <Page title="Team" subtitle="Invitations and roles stay inside this organization.">
      {can(tenant, 'members.manage') ? (
        <Card>
          <h2 className="mb-3 font-display text-lg font-semibold">Invite a member</h2>
          <Form onSubmit={onSubmit}>
            {error ? <Alert>{error}</Alert> : null}
            {inviteUrl ? <Alert tone="success">Invitation link (shown once): {inviteUrl}</Alert> : null}
            <Field label="Email" name="email" type="email" required />
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-semibold">Role</span>
              <select name="role_id" className="rounded-lg border border-line bg-surface px-3 py-2" required>
                {(roles.data || []).map((role) => (
                  <option key={role.id} value={role.id}>{role.name}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-semibold">Scope</span>
              <select name="scope" className="rounded-lg border border-line bg-surface px-3 py-2" defaultValue="BRANCHES">
                <option value="TENANT">Entire organization</option>
                <option value="BRANCHES">Assigned branches</option>
              </select>
            </label>
            <Button type="submit" disabled={invite.isPending}>Create invitation</Button>
          </Form>
        </Card>
      ) : null}
      <Card>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-line text-ink/60">
              <th className="py-2 font-medium">Name</th>
              <th className="py-2 font-medium">Email</th>
              <th className="py-2 font-medium">Roles</th>
              <th className="py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {(members.data?.results || []).map((member) => (
              <tr key={member.id} className="border-b border-line/70">
                <td className="py-2 font-semibold">{member.user.full_name}</td>
                <td className="py-2">{member.user.email}</td>
                <td className="py-2">{member.roles.map((r) => r.role_name).join(', ') || '—'}</td>
                <td className="py-2"><StatusPill value={member.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </Page>
  )
}
