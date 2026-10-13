import { useQuery } from '@tanstack/react-query'
import { listBalances } from '../../shared/api/stock.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { can } from '../../shared/permissions.ts'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { NoAccess } from '../../shared/ui/Feedback.tsx'
import { PageHeader, Panel } from '../../shared/ui/PageHeader.tsx'
import { useWorkspace } from '../workspace/queries.ts'

export function InventoryPage() {
  usePageTitle('Inventory')
  const workspace = useWorkspace()
  const context = workspace.data
  const balances = useQuery({ queryKey: ['balances'], queryFn: listBalances, enabled: Boolean(context) })
  if (!context) return null
  if (!can(context.permissions, 'inventory.view')) return <NoAccess />
  return (
    <div className="grid gap-6">
      <PageHeader
        title="Inventory"
        description="On-hand quantities come from the stock ledger. In transit is not available at the kitchen or the branch."
      />
      <Panel>
        <DataTable
          caption="Balances"
          rows={balances.data ?? []}
          rowKey={(row) => row.id}
          empty="No stock movements yet."
          columns={[
            { header: 'Location', render: (row) => <span className="font-medium">{row.location_name}</span> },
            { header: 'Item', render: (row) => `${row.item_name} (${row.item_sku})` },
            { header: 'On hand', render: (row) => `${row.quantity} ${row.base_unit}` },
          ]}
        />
      </Panel>
    </div>
  )
}
