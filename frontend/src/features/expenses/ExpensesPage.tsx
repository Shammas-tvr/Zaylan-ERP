import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useCreateExpense,
  useExpenseCategories,
  useExpenseSummary,
  useExpenses,
  useSubmitExpense,
  useWorkspace,
} from '../workspace/queries.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { formatDate } from '../../shared/labels.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { SelectField, TextArea, TextField } from '../../shared/ui/Field.tsx'
import { ErrorState, NoAccess, PageSkeleton } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'

export function ExpensesPage() {
  usePageTitle('Expenses')
  const workspace = useWorkspace()
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const expenses = useExpenses({ status: status || undefined, search: search || undefined })
  const summary = useExpenseSummary()
  const categories = useExpenseCategories()
  const createExpense = useCreateExpense()
  const submitExpense = useSubmitExpense()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    branch_id: '',
    category_id: '',
    amount: '',
    expense_date: new Date().toISOString().slice(0, 10),
    payment_method: 'OTHER',
    description: '',
    receipt: null as File | null,
  })

  const context = workspace.data
  const permissions = context?.permissions
  const entitled = (context?.subscription.features ?? []).includes('expenses')

  if (workspace.isLoading || expenses.isLoading) return <PageSkeleton />
  if (!context || !can(permissions, 'expenses.view')) return <NoAccess />
  if (!entitled) return <NoAccess>Expenses are not included in this plan.</NoAccess>
  if (expenses.isError) return <ErrorState error={expenses.error} onRetry={() => void expenses.refetch()} />

  const branches = context.branches.filter((b) => b.status === 'active')
  const canSubmit = can(permissions, 'expenses.submit')

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Expenses"
        description="Record branch expenses and track Brand Admin approval. Approval and payment are separate steps."
        action={
          canSubmit ? (
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
              New expense
            </Button>
          ) : null
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Pending approval" value={String(summary.data?.pending_approval ?? 0)} />
        <Metric label="Drafts" value={String(summary.data?.draft ?? 0)} />
        <Metric label="Approved" value={String(summary.data?.approved ?? 0)} />
        <Metric label="Pending amount" value={summary.data?.total_pending_amount ?? '0'} />
      </div>
      <Panel>
        <div className="mb-4 flex flex-wrap gap-3">
          <SelectField label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            <option value="draft">Draft</option>
            <option value="pending_approval">Pending approval</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="paid">Paid</option>
          </SelectField>
          <TextField
            label="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Category, branch, notes"
          />
        </div>
        <DataTable
          caption="Expenses"
          rows={expenses.data ?? []}
          rowKey={(row) => row.id}
          empty="No expenses yet."
          columns={[
            {
              header: 'Date',
              render: (row) => (
                <Link className="font-medium underline-offset-2 hover:underline" to={`/expenses/${row.id}`}>
                  {formatDate(row.expense_date)}
                </Link>
              ),
            },
            { header: 'Branch', render: (row) => row.branch_name },
            { header: 'Category', render: (row) => row.category_name },
            { header: 'Amount', render: (row) => row.amount },
            { header: 'Status', render: (row) => <StatusBadge status={row.status} /> },
            {
              header: 'Action',
              render: (row) =>
                canSubmit && row.status === 'draft' ? (
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={submitExpense.isPending}
                    onClick={() => submitExpense.mutate(row.id)}
                  >
                    Submit
                  </Button>
                ) : (
                  '—'
                ),
            },
          ]}
        />
      </Panel>

      <Modal open={open} title="New expense" onClose={() => setOpen(false)}>
        <form
          className="grid gap-3"
          onSubmit={(event) => {
            event.preventDefault()
            createExpense.mutate(form, { onSuccess: () => setOpen(false) })
          }}
        >
          <SelectField
            label="Branch"
            required
            value={form.branch_id}
            onChange={(e) => setForm({ ...form, branch_id: e.target.value })}
          >
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Category"
            required
            value={form.category_id}
            onChange={(e) => setForm({ ...form, category_id: e.target.value })}
          >
            {(categories.data ?? [])
              .filter((c) => c.is_active)
              .map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
          </SelectField>
          <TextField
            label="Amount"
            required
            type="number"
            min="0"
            step="0.01"
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
          />
          <TextField
            label="Date"
            required
            type="date"
            value={form.expense_date}
            onChange={(e) => setForm({ ...form, expense_date: e.target.value })}
          />
          <SelectField
            label="Payment method"
            value={form.payment_method}
            onChange={(e) => setForm({ ...form, payment_method: e.target.value })}
          >
            <option value="CASH">Cash</option>
            <option value="BANK_TRANSFER">Bank transfer</option>
            <option value="UPI">UPI</option>
            <option value="CARD">Card</option>
            <option value="CHEQUE">Cheque</option>
            <option value="OTHER">Other</option>
          </SelectField>
          <TextArea
            label="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
          <TextField
            label="Receipt"
            type="file"
            accept="image/*,.pdf"
            onChange={(e) => setForm({ ...form, receipt: e.target.files?.[0] ?? null })}
          />
          {createExpense.isError ? <p className="text-sm text-danger">{errorMessage(createExpense.error)}</p> : null}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createExpense.isPending || !form.category_id}>
              Save draft
            </Button>
          </div>
        </form>
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
