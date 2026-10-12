import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  useApproveExpense,
  useExpense,
  useMarkExpensePaid,
  useRejectExpense,
  useSubmitExpense,
  useWorkspace,
} from '../workspace/queries.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { formatDate, formatWhen } from '../../shared/labels.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { TextArea, TextField } from '../../shared/ui/Field.tsx'
import { ErrorState, NoAccess, PageSkeleton } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'

export function ExpenseDetailPage() {
  usePageTitle('Expense')
  const { expenseId = '' } = useParams()
  const workspace = useWorkspace()
  const expense = useExpense(expenseId)
  const submit = useSubmitExpense()
  const approve = useApproveExpense()
  const reject = useRejectExpense()
  const pay = useMarkExpensePaid()
  const [rejectOpen, setRejectOpen] = useState(false)
  const [reason, setReason] = useState('')
  const [payRef, setPayRef] = useState('')

  if (workspace.isLoading || expense.isLoading) return <PageSkeleton />
  if (!can(workspace.data?.permissions, 'expenses.view')) return <NoAccess />
  if (expense.isError) return <ErrorState error={expense.error} onRetry={() => void expense.refetch()} />
  const row = expense.data
  if (!row) return null

  const permissions = workspace.data?.permissions

  return (
    <div className="grid gap-6">
      <PageHeader
        title={`${row.category_name} · ${row.amount}`}
        description={`${row.branch_name} · ${formatDate(row.expense_date)}`}
        action={
          <Link to="/expenses" className="text-sm text-ink-soft underline-offset-2 hover:underline">
            Back to expenses
          </Link>
        }
      />
      <Panel>
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={row.status} />
          <span className="text-sm text-ink-soft">{row.entry_type === 'recurring' ? 'Recurring' : 'Variable'}</span>
        </div>
        <dl className="mt-5 grid gap-3 sm:grid-cols-2">
          <Fact label="Payment method" value={row.payment_method} />
          <Fact label="Billing period" value={row.billing_period || '—'} />
          <Fact label="Submitted by" value={row.submitted_by_name || row.submitted_by_email || '—'} />
          <Fact label="Submitted at" value={row.submitted_at ? formatWhen(row.submitted_at) : '—'} />
          <Fact label="Approved by" value={row.approved_by_email || '—'} />
          <Fact label="Approved at" value={row.approved_at ? formatWhen(row.approved_at) : '—'} />
          <Fact label="Rejected at" value={row.rejected_at ? formatWhen(row.rejected_at) : '—'} />
          <Fact label="Paid at" value={row.paid_at ? formatWhen(row.paid_at) : '—'} />
        </dl>
        {row.description ? <p className="mt-4 whitespace-pre-wrap text-sm">{row.description}</p> : null}
        {row.rejection_reason ? (
          <p className="mt-4 rounded-xl bg-danger-soft p-3 text-sm text-danger">Rejection: {row.rejection_reason}</p>
        ) : null}
        {row.receipt_url ? (
          <p className="mt-4 text-sm">
            <a className="underline" href={row.receipt_url} target="_blank" rel="noreferrer">
              View receipt
            </a>
          </p>
        ) : null}
        <div className="mt-6 flex flex-wrap gap-2">
          {can(permissions, 'expenses.submit') && (row.status === 'draft' || row.status === 'rejected') ? (
            <Button disabled={submit.isPending} onClick={() => submit.mutate(row.id)}>
              Submit for approval
            </Button>
          ) : null}
          {can(permissions, 'expenses.approve') && row.status === 'pending_approval' ? (
            <>
              <Button disabled={approve.isPending} onClick={() => approve.mutate(row.id)}>
                Approve
              </Button>
              <Button variant="danger" onClick={() => setRejectOpen(true)}>
                Reject
              </Button>
            </>
          ) : null}
          {can(permissions, 'expenses.pay') && row.status === 'approved' ? (
            <form
              className="flex flex-wrap items-end gap-2"
              onSubmit={(event) => {
                event.preventDefault()
                pay.mutate({ id: row.id, payment_reference: payRef })
              }}
            >
              <TextField label="Payment reference" value={payRef} onChange={(e) => setPayRef(e.target.value)} />
              <Button type="submit" disabled={pay.isPending}>
                Mark paid
              </Button>
            </form>
          ) : null}
        </div>
        {approve.isError || reject.isError || submit.isError || pay.isError ? (
          <p className="mt-3 text-sm text-danger">
            {errorMessage(approve.error || reject.error || submit.error || pay.error)}
          </p>
        ) : null}
      </Panel>
      <Modal open={rejectOpen} title="Reject expense" onClose={() => setRejectOpen(false)}>
        <TextArea label="Reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setRejectOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={!reason.trim() || reject.isPending}
            onClick={() =>
              reject.mutate({ id: row.id, reason }, { onSuccess: () => setRejectOpen(false) })
            }
          >
            Reject
          </Button>
        </div>
      </Modal>
    </div>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-soft">{label}</dt>
      <dd className="mt-1 font-medium">{value}</dd>
    </div>
  )
}
