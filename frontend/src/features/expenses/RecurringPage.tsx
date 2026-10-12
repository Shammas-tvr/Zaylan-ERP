import { useState } from 'react'
import {
  useCreateExpenseCategory,
  useCreateRecurringExpense,
  useExpenseCategories,
  useRecurringExpenses,
  useWorkspace,
} from '../workspace/queries.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { SelectField, TextField } from '../../shared/ui/Field.tsx'
import { NoAccess, PageSkeleton } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'

export function RecurringPage() {
  usePageTitle('Recurring expenses')
  const workspace = useWorkspace()
  const recurring = useRecurringExpenses()
  const categories = useExpenseCategories()
  const createRecurring = useCreateRecurringExpense()
  const createCategory = useCreateExpenseCategory()
  const [open, setOpen] = useState(false)
  const [catOpen, setCatOpen] = useState(false)
  const [form, setForm] = useState({
    branch_id: '',
    category_id: '',
    expected_amount: '',
    start_date: new Date().toISOString().slice(0, 10),
    end_date: '',
    due_day: '1',
    description: '',
  })
  const [catForm, setCatForm] = useState({ code: '', name: '' })

  if (workspace.isLoading || recurring.isLoading) return <PageSkeleton />
  if (!can(workspace.data?.permissions, 'expenses.configure')) return <NoAccess />
  if (!(workspace.data?.subscription.features ?? []).includes('expenses')) {
    return <NoAccess>Expenses are not included in this plan.</NoAccess>
  }

  const branches = workspace.data?.branches.filter((b) => b.status === 'active') ?? []

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Recurring expenses"
        description="Configure fixed monthly costs. The system generates pending entries for Brand Admin approval — never auto-approved or paid."
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setCatOpen(true)}>
              Add category
            </Button>
            <Button
              onClick={() => {
                setForm((prev) => ({
                  ...prev,
                  branch_id: branches[0]?.id ?? '',
                  category_id: categories.data?.[0]?.id ?? '',
                }))
                setOpen(true)
              }}
            >
              Add recurring
            </Button>
          </div>
        }
      />
      <Panel>
        <DataTable
          caption="Recurring templates"
          rows={recurring.data ?? []}
          rowKey={(row) => row.id}
          empty="No recurring expenses configured."
          columns={[
            { header: 'Branch', render: (row) => row.branch_name },
            { header: 'Category', render: (row) => row.category_name },
            { header: 'Amount', render: (row) => row.expected_amount },
            { header: 'Due day', render: (row) => String(row.due_day) },
            {
              header: 'Status',
              render: (row) => <StatusBadge status={row.is_active ? 'active' : 'inactive'} />,
            },
          ]}
        />
      </Panel>

      <Modal open={open} title="Recurring expense" onClose={() => setOpen(false)}>
        <form
          className="grid gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            createRecurring.mutate(
              {
                ...form,
                due_day: Number(form.due_day),
                end_date: form.end_date || undefined,
              },
              { onSuccess: () => setOpen(false) },
            )
          }}
        >
          <SelectField label="Branch" value={form.branch_id} onChange={(e) => setForm({ ...form, branch_id: e.target.value })}>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Category"
            value={form.category_id}
            onChange={(e) => setForm({ ...form, category_id: e.target.value })}
          >
            {(categories.data ?? []).map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </SelectField>
          <TextField
            label="Expected amount"
            type="number"
            min="0"
            step="0.01"
            required
            value={form.expected_amount}
            onChange={(e) => setForm({ ...form, expected_amount: e.target.value })}
          />
          <TextField
            label="Start date"
            type="date"
            required
            value={form.start_date}
            onChange={(e) => setForm({ ...form, start_date: e.target.value })}
          />
          <TextField
            label="End date"
            type="date"
            value={form.end_date}
            onChange={(e) => setForm({ ...form, end_date: e.target.value })}
          />
          <TextField
            label="Due day (1–28)"
            type="number"
            min="1"
            max="28"
            value={form.due_day}
            onChange={(e) => setForm({ ...form, due_day: e.target.value })}
          />
          <TextField
            label="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          {createRecurring.isError ? (
            <p className="text-sm text-danger">{errorMessage(createRecurring.error)}</p>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createRecurring.isPending}>
              Save
            </Button>
          </div>
        </form>
      </Modal>

      <Modal open={catOpen} title="Expense category" onClose={() => setCatOpen(false)}>
        <form
          className="grid gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            createCategory.mutate(catForm, {
              onSuccess: () => {
                setCatOpen(false)
                setCatForm({ code: '', name: '' })
              },
            })
          }}
        >
          <TextField
            label="Code"
            required
            value={catForm.code}
            onChange={(e) => setCatForm({ ...catForm, code: e.target.value.toUpperCase() })}
          />
          <TextField
            label="Name"
            required
            value={catForm.name}
            onChange={(e) => setCatForm({ ...catForm, name: e.target.value })}
          />
          {createCategory.isError ? (
            <p className="text-sm text-danger">{errorMessage(createCategory.error)}</p>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setCatOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createCategory.isPending}>
              Save
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
