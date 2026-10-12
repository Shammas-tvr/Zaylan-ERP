import { useState } from 'react'
import { useInvitations, useMembers, useRevokeInvitation, useRoles, useSendInvitation, useWorkspace } from '../workspace/queries.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { formatWhen } from '../../shared/labels.ts'
import { can, permissionCatalog } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { SelectField, TextField } from '../../shared/ui/Field.tsx'
import { NoAccess, Notice } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'

const tabs = [
  { id: 'members', label: 'Members' },
  { id: 'invitations', label: 'Invitations' },
  { id: 'roles', label: 'Roles' },
] as const

export function PeoplePage() {
  usePageTitle('People')
  const workspace = useWorkspace()
  const context = workspace.data
  const allowed = can(context?.permissions, 'members.view')
  const canManage = can(context?.permissions, 'members.manage')
  const canViewRoles = can(context?.permissions, 'roles.view')
  const members = useMembers(allowed)
  const roles = useRoles(canViewRoles || canManage)
  const [tab, setTab] = useState<(typeof tabs)[number]['id']>('members')
  const [open, setOpen] = useState(false)
  const visibleTabs = tabs.filter((item) => {
    if (item.id === 'invitations') return canManage
    if (item.id === 'roles') return canViewRoles
    return true
  })

  if (!context) return null
  if (!allowed) return <NoAccess />

  return (
    <div className="grid gap-6">
      <PageHeader
        title="People"
        description="Roles decide what a person can do. Branch access decides where they can do it."
        action={
          canManage ? (
            <Button onClick={() => setOpen(true)}>Invite person</Button>
          ) : null
        }
      />
      <div className="flex gap-2" role="tablist" aria-label="People">
        {visibleTabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={`h-10 rounded-full px-4 text-sm ${tab === item.id ? 'bg-[var(--brand-primary)] text-[var(--brand-on-primary)]' : 'bg-[var(--brand-surface)] text-ink'}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {tab === 'members' ? (
        <Panel>
          <DataTable
            caption="Members"
            rows={members.data ?? []}
            rowKey={(member) => member.id}
            empty="No members yet."
            columns={[
              { header: 'Name', render: (member) => <span className="font-medium">{member.full_name}</span> },
              { header: 'Email', render: (member) => member.email },
              { header: 'Branches', render: (member) => member.branches.join(', ') },
              { header: 'Roles', render: (member) => member.roles.join(', ') },
              { header: 'Status', render: (member) => <StatusBadge status={member.status} /> },
            ]}
          />
        </Panel>
      ) : null}
      {tab === 'invitations' ? <Invitations timezone={context.organization.timezone} /> : null}
      {tab === 'roles' ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {(roles.data ?? []).map((role) => (
            <Panel key={role.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-display text-2xl">{role.name}</h2>
                  <p className="mt-1 text-sm text-ink-soft">{role.description}</p>
                </div>
                {role.is_system ? <span className="rounded-full bg-cream px-2.5 py-1 text-xs font-medium text-ink-soft">Default</span> : null}
              </div>
              <ul className="mt-4 grid gap-1 text-sm text-ink-soft">
                {role.permissions.slice(0, 6).map((code) => (
                  <li key={code}>{permissionCatalog[code]?.name ?? code}</li>
                ))}
              </ul>
              {role.permissions.length > 6 ? (
                <p className="mt-2 text-sm text-ink-soft">{role.permissions.length - 6} more permissions</p>
              ) : null}
            </Panel>
          ))}
        </div>
      ) : null}
      {open ? (
        <InviteModal
          roles={(roles.data ?? []).map((role) => ({ id: role.id, name: role.name }))}
          branches={context.branches.map((branch) => ({ id: branch.id, name: branch.name }))}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </div>
  )
}

function Invitations({ timezone }: { timezone: string }) {
  const invitations = useInvitations()
  const revoke = useRevokeInvitation()
  return (
    <Panel>
      <DataTable
        caption="Invitations"
        rows={invitations.data ?? []}
        rowKey={(invitation) => invitation.id}
        empty="No invitations."
        columns={[
          { header: 'Email', render: (invitation) => invitation.email },
          { header: 'Role', render: (invitation) => invitation.role_name },
          { header: 'Expires', render: (invitation) => formatWhen(invitation.expires_at, timezone) },
          { header: 'Status', render: (invitation) => <StatusBadge status={invitation.status} /> },
          {
            header: 'Action',
            render: (invitation) =>
              invitation.status === 'pending' ? (
                <Button size="sm" variant="secondary" onClick={() => revoke.mutate(invitation.id)}>
                  Revoke
                </Button>
              ) : (
                '—'
              ),
          },
        ]}
      />
    </Panel>
  )
}

function InviteModal({
  roles,
  branches,
  onClose,
}: {
  roles: Array<{ id: string; name: string }>
  branches: Array<{ id: string; name: string }>
  onClose: () => void
}) {
  const send = useSendInvitation()
  const [email, setEmail] = useState('')
  const [roleId, setRoleId] = useState(roles[0]?.id ?? '')
  const [branchIds, setBranchIds] = useState<string[]>([])
  const [notice, setNotice] = useState<string | null>(null)

  return (
    <Modal open title="Invite person" onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          send.mutate(
            { email, role_id: roleId, branch_ids: branchIds },
            {
              onSuccess: () => setNotice(`Invitation prepared for ${email}.`),
            },
          )
        }}
      >
        <TextField label="Email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
        <SelectField label="Role" value={roleId} onChange={(event) => setRoleId(event.target.value)}>
          {roles.map((role) => (
            <option key={role.id} value={role.id}>
              {role.name}
            </option>
          ))}
        </SelectField>
        <fieldset className="grid gap-2">
          <legend className="text-sm font-medium">Branches</legend>
          <p className="text-sm text-ink-soft">Leave this empty for access across the organization.</p>
          {branches.map((branch) => (
            <label key={branch.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={branchIds.includes(branch.id)}
                onChange={(event) =>
                  setBranchIds((current) =>
                    event.target.checked ? [...current, branch.id] : current.filter((id) => id !== branch.id),
                  )
                }
              />
              {branch.name}
            </label>
          ))}
        </fieldset>
        {notice ? <Notice>{notice}</Notice> : null}
        {send.isError ? <p className="text-sm text-danger">{errorMessage(send.error)}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
          <Button type="submit" disabled={send.isPending || !roleId}>
            {send.isPending ? 'Sending…' : 'Send invitation'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
