import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { updateBranchLogin } from '../../shared/api/workspace.ts'
import { useCreateBranch, useSession, useWorkspace } from '../workspace/queries.ts'
import type { BranchInput } from '../../shared/api/types.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { PasswordField, TextField } from '../../shared/ui/Field.tsx'
import { NoAccess, Notice } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'

const emptyBranch = (timezone: string): BranchInput => ({
  name: '',
  code: '',
  timezone,
  phone: '',
  email: '',
  address: '',
  login_username: '',
  login_password: '',
})

export function BranchesPage() {
  usePageTitle('Branches')
  const workspace = useWorkspace()
  const session = useSession()
  const context = workspace.data
  const [open, setOpen] = useState(false)
  const [resetOpen, setResetOpen] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [form, setForm] = useState<BranchInput>(emptyBranch('Asia/Kolkata'))
  const create = useCreateBranch()

  if (!context) return null
  if (!can(context.permissions, 'branches.view')) return <NoAccess />

  const rows = session.branchId ? context.branches.filter((branch) => branch.id === session.branchId) : context.branches
  const canManage = can(context.permissions, 'branches.manage')

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Branches"
        description="Each branch keeps its own operations. People only see the branches they are allowed to use."
        action={
          canManage ? (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setResetOpen(true)}>
                Branch password
              </Button>
              <Button
                onClick={() => {
                  setForm(emptyBranch(context.organization.timezone))
                  setOpen(true)
                }}
              >
                New branch
              </Button>
            </div>
          ) : null
        }
      />
      {notice ? <Notice>{notice}</Notice> : null}
      <Panel>
        <DataTable
          caption="Branches"
          rows={rows}
          rowKey={(branch) => branch.id}
          empty="No branches yet."
          columns={[
            { header: 'Branch', render: (branch) => <span className="font-medium">{branch.name}</span> },
            { header: 'Code', render: (branch) => branch.code },
            { header: 'Status', render: (branch) => <StatusBadge status={branch.status} /> },
            { header: 'Timezone', render: (branch) => branch.timezone || context.organization.timezone },
            { header: 'Address', render: (branch) => branch.address || '—' },
            { header: 'Login', render: (branch) => branch.username || '—' },
          ]}
        />
      </Panel>
      {resetOpen ? (
        <PasswordModal
          branches={rows}
          onClose={() => setResetOpen(false)}
          onSaved={(name) => {
            setResetOpen(false)
            setNotice(`Password updated for ${name}.`)
          }}
        />
      ) : null}
      <Modal open={open} title="New branch" onClose={() => setOpen(false)}>
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            create.mutate(form, {
              onSuccess: (branch) => {
                setOpen(false)
                setNotice(`${branch.name} was added.`)
              },
            })
          }}
        >
          <TextField label="Name" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          <TextField
            label="Code"
            required
            hint="A short code unique inside this organization, such as BH."
            value={form.code}
            onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
          />
          <TextField label="Timezone" value={form.timezone} onChange={(event) => setForm({ ...form, timezone: event.target.value })} />
          <TextField label="Phone" value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
          <TextField label="Address" value={form.address} onChange={(event) => setForm({ ...form, address: event.target.value })} />
          <TextField
            label="Branch username"
            required
            minLength={3}
            value={form.login_username ?? ''}
            onChange={(event) => setForm({ ...form, login_username: event.target.value.trim() })}
            hint="This branch signs in with this username at the brand portal."
          />
          <PasswordField
            required
            value={form.login_password ?? ''}
            onChange={(event) => setForm({ ...form, login_password: event.target.value })}
          />
          {create.isError ? <p className="text-sm text-danger">{errorMessage(create.error)}</p> : null}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? 'Saving…' : 'Save branch'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}

function PasswordModal({
  branches,
  onClose,
  onSaved,
}: {
  branches: Array<{ id: string; name: string; username?: string }>
  onClose: () => void
  onSaved: (name: string) => void
}) {
  const queryClient = useQueryClient()
  const [branchId, setBranchId] = useState(branches[0]?.id ?? '')
  const [username, setUsername] = useState(branches[0]?.username ?? '')
  const [password, setPassword] = useState('')
  const selected = branches.find((branch) => branch.id === branchId)
  const save = useMutation({
    mutationFn: () =>
      updateBranchLogin(branchId, {
        login_password: password,
        login_username: selected?.username ? undefined : username,
      }),
    onSuccess: async (branch) => {
      await queryClient.invalidateQueries({ queryKey: ['context'] })
      onSaved(branch.name)
    },
  })
  return (
    <Modal open title="Branch password" onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        <label className="grid gap-1.5 text-sm">
          <span className="font-medium">Branch</span>
          <select
            className="h-11 rounded-xl border border-line bg-cream px-3"
            value={branchId}
            onChange={(event) => {
              const next = branches.find((branch) => branch.id === event.target.value)
              setBranchId(event.target.value)
              setUsername(next?.username ?? '')
            }}
          >
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </select>
        </label>
        <TextField
          label="Username"
          required
          minLength={3}
          disabled={Boolean(selected?.username)}
          value={selected?.username || username}
          onChange={(event) => setUsername(event.target.value.trim())}
        />
        <PasswordField required value={password} onChange={(event) => setPassword(event.target.value)} />
        {save.isError ? <p className="text-sm text-danger">{errorMessage(save.error)}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={save.isPending || !branchId}>Save</Button>
        </div>
      </form>
    </Modal>
  )
}
