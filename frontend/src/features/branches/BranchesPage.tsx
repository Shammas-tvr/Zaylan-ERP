import { useState } from 'react'
import { useCreateBranch, useSession, useWorkspace } from '../workspace/queries.ts'
import type { BranchInput } from '../../shared/api/types.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { TextField } from '../../shared/ui/Field.tsx'
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
})

export function BranchesPage() {
  usePageTitle('Branches')
  const workspace = useWorkspace()
  const session = useSession()
  const context = workspace.data
  const [open, setOpen] = useState(false)
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
            <Button
              onClick={() => {
                setForm(emptyBranch(context.organization.timezone))
                setOpen(true)
              }}
            >
              New branch
            </Button>
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
          ]}
        />
      </Panel>
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
