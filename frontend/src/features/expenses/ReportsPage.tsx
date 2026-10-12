import { useExpenseReport, useWorkspace } from '../workspace/queries.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { labelOf, statusLabel } from '../../shared/labels.ts'
import { can } from '../../shared/permissions.ts'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { NoAccess, PageSkeleton } from '../../shared/ui/Feedback.tsx'
import { PageHeader, Panel } from '../../shared/ui/PageHeader.tsx'

export function ExpenseReportsPage() {
  usePageTitle('Expense reports')
  const workspace = useWorkspace()
  const report = useExpenseReport()

  if (workspace.isLoading || report.isLoading) return <PageSkeleton />
  if (!can(workspace.data?.permissions, 'expenses.view')) return <NoAccess />
  if (!(workspace.data?.subscription.features ?? []).includes('expenses')) {
    return <NoAccess>Expenses are not included in this plan.</NoAccess>
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Expense reports"
        description="Branch-wise totals by status across the brand."
      />
      <Panel>
        <DataTable
          caption="By branch"
          rows={report.data ?? []}
          rowKey={(row) => `${row.branch_id}-${row.status}`}
          empty="No expense activity yet."
          columns={[
            { header: 'Branch', render: (row) => row.branch_name },
            { header: 'Status', render: (row) => labelOf(statusLabel, row.status) },
            { header: 'Count', render: (row) => String(row.count) },
            { header: 'Total', render: (row) => row.total_amount },
          ]}
        />
      </Panel>
    </div>
  )
}
