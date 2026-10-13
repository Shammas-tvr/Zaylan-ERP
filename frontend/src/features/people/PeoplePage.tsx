import { useState } from 'react'
import { useCreateStaff, useMembers, useRoles, useWorkspace } from '../workspace/queries.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { can, permissionCatalog } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { PasswordField, SelectField, TextField } from '../../shared/ui/Field.tsx'
import { NoAccess, Notice } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'

const tabs = [
  { id: 'members', label: 'Members' },
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
    if (item.id === 'roles') return canViewRoles
    return true
  })

  if (!context) return null
  if (!allowed) return <NoAccess />

  return (
    <div className="grid gap-6">
      <PageHeader
        title="People"
        description="Create brand staff with username and password. Roles decide what they can do."
        action={
          canManage ? (
            <Button onClick={() => setOpen(true)}>Add staff</Button>
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
              {
                header: 'Login',
                render: (member) =>
                  member.email.includes('.staff.zaylan.local')
                    ? member.email.split('@')[0]
                    : member.email,
              },
              { header: 'Branches', render: (member) => member.branches.join(', ') },
              { header: 'Roles', render: (member) => member.roles.join(', ') },
              { header: 'Status', render: (member) => <StatusBadge status={member.status} /> },
            ]}
          />
        </Panel>
      ) : null}
      {tab === 'roles' ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {(roles.data ?? []).map((role) => (
            <Panel key={role.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-display text-2xl">{role.name}</h2>
                  <p className="mt-1 text-sm text-ink-soft">{role.description}</p>
                </div>
                {role.is_system ? (
                  <span className="rounded-full bg-cream px-2.5 py-1 text-xs font-medium text-ink-soft">
                    Default
                  </span>
                ) : null}
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
        <StaffModal
          roles={(roles.data ?? [])
            .filter((role) => role.name.toLowerCase() !== 'owner / admin')
            .map((role) => ({ id: role.id, name: role.name }))}
          branches={context.branches.map((branch) => ({ id: branch.id, name: branch.name }))}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </div>
  )
}

function StaffModal({
  roles,
  branches,
  onClose,
}: {
  roles: Array<{ id: string; name: string }>
  branches: Array<{ id: string; name: string }>
  onClose: () => void
}) {
  const create = useCreateStaff()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [roleId, setRoleId] = useState(roles[0]?.id ?? '')
  const [branchIds, setBranchIds] = useState<string[]>([])
  const [notice, setNotice] = useState<string | null>(null)

  return (
    <Modal open title="Add staff" onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate(
            {
              username,
              password,
              full_name: fullName,
              role_id: roleId,
              branch_ids: branchIds,
            },
            {
              onSuccess: () => {
                setNotice(`Staff account “${username}” created.`)
                setUsername('')
                setPassword('')
                setFullName('')
              },
            },
          )
        }}
      >
        <TextField
          label="Full name"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
        />
        <TextField
          label="Username"
          required
          minLength={3}
          value={username}
          onChange={(event) => setUsername(event.target.value.trim())}
          hint="Staff sign in with this username at /login."
        />
        <PasswordField
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <SelectField label="Role" value={roleId} onChange={(event) => setRoleId(event.target.value)}>
          {roles.map((role) => (
            <option key={role.id} value={role.id}>
              {role.name}
            </option>
          ))}
        </SelectField>
        <fieldset className="grid gap-2">
          <legend className="text-sm font-medium">Branches</legend>
          <p className="text-sm text-ink-soft">Leave empty for brand-wide access when the role allows it.</p>
          {branches.map((branch) => (
            <label key={branch.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={branchIds.includes(branch.id)}
                onChange={(event) =>
                  setBranchIds((current) =>
                    event.target.checked
                      ? [...current, branch.id]
                      : current.filter((id) => id !== branch.id),
                  )
                }
              />
              {branch.name}
            </label>
          ))}
        </fieldset>
        {notice ? <Notice>{notice}</Notice> : null}
        {create.isError ? <p className="text-sm text-danger">{errorMessage(create.error)}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
          <Button type="submit" disabled={create.isPending || !roleId}>
            {create.isPending ? 'Creating…' : 'Create staff'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
