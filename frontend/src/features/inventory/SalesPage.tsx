import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listItems, listSales, recordSale, refundSale } from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { TextField } from '../../shared/ui/Field.tsx'
import { NoAccess } from '../../shared/ui/Feedback.tsx'
import { PageHeader, Panel } from '../../shared/ui/PageHeader.tsx'
import { useSession, useWorkspace } from '../workspace/queries.ts'

export function SalesPage() {
  usePageTitle('Sales')
  const workspace = useWorkspace()
  const session = useSession()
  const context = workspace.data
  const sales = useQuery({ queryKey: ['sales'], queryFn: listSales, enabled: Boolean(context) })
  const items = useQuery({
    queryKey: ['items'],
    queryFn: listItems,
    enabled: Boolean(context && can(context.permissions, 'pos.sell')),
  })
  const queryClient = useQueryClient()
  const [itemId, setItemId] = useState('')
  const [quantity, setQuantity] = useState('1')
  const finished = (items.data ?? []).filter((item) => item.kind === 'FINISHED')
  const selected = itemId || finished[0]?.id || ''
  const branchId = session.branchId || context?.branches[0]?.id || ''
  const sell = useMutation({
    mutationFn: () =>
      recordSale({
        branch_id: branchId,
        idempotency_key: crypto.randomUUID(),
        lines: [{ item_id: selected, quantity }],
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sales'] })
      await queryClient.invalidateQueries({ queryKey: ['balances'] })
    },
  })
  const refund = useMutation({
    mutationFn: refundSale,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['sales'] })
      await queryClient.invalidateQueries({ queryKey: ['balances'] })
    },
  })
  if (!context) return null
  if (!can(context.permissions, 'sales.view') && !can(context.permissions, 'pos.sell')) return <NoAccess />

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Sales"
        description="A completed sale deducts the recipe lines marked for sale, once. Refund puts that stock back."
      />
      {can(context.permissions, 'pos.sell') ? (
        <Panel>
          <form
            className="grid gap-4 sm:grid-cols-[1fr_140px_auto] sm:items-end"
            onSubmit={(event) => {
              event.preventDefault()
              sell.mutate()
            }}
          >
            <label className="grid gap-1.5 text-sm">
              <span className="font-medium">Product</span>
              <select className="h-11 rounded-xl border border-line bg-cream px-3" value={selected} onChange={(event) => setItemId(event.target.value)}>
                {finished.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
            <TextField label="Quantity" required value={quantity} onChange={(event) => setQuantity(event.target.value)} />
            <Button type="submit" disabled={sell.isPending || !selected || !branchId}>Record sale</Button>
          </form>
          {sell.isError ? <p className="mt-3 text-sm text-danger">{errorMessage(sell.error)}</p> : null}
        </Panel>
      ) : null}
      <Panel>
        <DataTable
          caption="Sales"
          rows={sales.data ?? []}
          rowKey={(sale) => sale.id}
          empty="No sales yet."
          columns={[
            { header: 'Branch', render: (sale) => <span className="font-medium">{sale.branch_name}</span> },
            {
              header: 'Items',
              render: (sale) => sale.lines.map((line) => `${line.quantity} ${line.item_name}`).join(', '),
            },
            { header: 'Status', render: (sale) => sale.status },
            {
              header: '',
              render: (sale) =>
                sale.status === 'COMPLETED' && can(context.permissions, 'pos.refund') ? (
                  <Button size="sm" variant="secondary" disabled={refund.isPending} onClick={() => refund.mutate(sale.id)}>
                    Refund
                  </Button>
                ) : null,
            },
          ]}
        />
        {refund.isError ? <p className="mt-3 text-sm text-danger">{errorMessage(refund.error)}</p> : null}
      </Panel>
    </div>
  )
}
