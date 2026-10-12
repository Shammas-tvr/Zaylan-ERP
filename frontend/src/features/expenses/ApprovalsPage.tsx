import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useApproveExpense,
  useExpenses,
  useRejectExpense,
  useWorkspace,
} from '../workspace/queries.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { formatWhen } from '../../shared/labels.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { TextArea } from '../../shared/ui/Field.tsx'
import { NoAccess, PageSkeleton } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel } from '../../shared/ui/PageHeader.tsx'

export function ApprovalsPage() {
  usePageTitle('Approvals')
  const workspace = useWorkspace()
  const expenses = useExpenses({ status: 'pending_approval' })
  const [rejectId, setRejectId] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const approve = useApproveExpense()
  const reject = useRejectExpense()

  if (workspace.isLoading || expenses.isLoading) return <PageSkeleton />
  if (!can(workspace.data?.permissions, 'expenses.approve')) return <NoAccess />
  if (!(workspace.data?.subscription.features ?? []).includes('expenses')) {
    return <NoAccess>Expenses are not included in this plan.</NoAccess>
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Approvals"
        description="Review expenses submitted by branches. You cannot approve your own submissions."
      />
      <Panel>
        <DataTable
          caption="Pending approvals"
          rows={expenses.data ?? []}
          rowKey={(row) => row.id}
          empty="Nothing waiting for approval."
          columns={[
            {
              header: 'Expense',
              render: (row) => (
                <Link className="font-medium underline-offset-2 hover:underline" to={`/expenses/${row.id}`}>
                  {row.category_name} · {row.amount}
                </Link>
              ),
            },
            { header: 'Branch', render: (row) => row.branch_name },
            {
              header: 'Submitted',
              render: (row) => (row.submitted_at ? formatWhen(row.submitted_at) : '—'),
            },
            {
              header: 'By',
              render: (row) => row.submitted_by_name || row.submitted_by_email || '—',
            },
            {
              header: 'Action',
              render: (row) => (
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" disabled={approve.isPending} onClick={() => approve.mutate(row.id)}>
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    onClick={() => {
                      setRejectId(row.id)
                      setReason('')
                    }}
                  >
                    Reject
                  </Button>
                </div>
              ),
            },
          ]}
        />
      </Panel>
      <Modal open={Boolean(rejectId)} title="Reject expense" onClose={() => setRejectId(null)}>
        <TextArea label="Reason" required value={reason} onChange={(e) => setReason(e.target.value)} />
        {reject.isError ? <p className="mt-2 text-sm text-danger">{errorMessage(reject.error)}</p> : null}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setRejectId(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={!reason.trim() || reject.isPending}
            onClick={() => {
              if (!rejectId) return
              reject.mutate({ id: rejectId, reason }, { onSuccess: () => setRejectId(null) })
            }}
          >
            Reject
          </Button>
        </div>
      </Modal>
    </div>
  )
}
