import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  approveTransfer,
  createTransfer,
  dispatchTransfer,
  listItems,
  listTransfers,
  receiveTransfer,
} from '../../shared/api/stock.ts'
import type { Transfer } from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { TextField } from '../../shared/ui/Field.tsx'
import { NoAccess } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'
import { useWorkspace } from '../workspace/queries.ts'

export function TransfersPage() {
  usePageTitle('Transfers')
  const workspace = useWorkspace()
  const context = workspace.data
  const transfers = useQuery({ queryKey: ['transfers'], queryFn: listTransfers, enabled: Boolean(context) })
  const [open, setOpen] = useState(false)
  const [receiving, setReceiving] = useState<Transfer | null>(null)
  if (!context) return null
  if (!can(context.permissions, 'inventory.view')) return <NoAccess />
  const canDispatch = can(context.permissions, 'inventory.dispatch')
  const canReceive = can(context.permissions, 'inventory.receive')

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Transfers"
        description="Dispatch moves stock into transit. The branch balance changes only after the branch confirms what arrived."
        action={canDispatch ? <Button onClick={() => setOpen(true)}>New transfer</Button> : null}
      />
      <Panel>
        <DataTable
          caption="Transfers"
          rows={transfers.data ?? []}
          rowKey={(row) => row.id}
          empty="No transfers yet."
          columns={[
            { header: 'Number', render: (row) => <span className="font-medium">{row.number}</span> },
            { header: 'To', render: (row) => row.destination_name },
            { header: 'Status', render: (row) => <StatusBadge status={row.status.toLowerCase()} /> },
            {
              header: 'Lines',
              render: (row) =>
                row.lines
                  .map((line) => {
                    const received = line.received_quantity == null ? '' : ` / received ${line.received_quantity}`
                    return `${line.item_name} ${line.dispatched_quantity || line.requested_quantity} ${line.unit}${received}`
                  })
                  .join(', '),
            },
            {
              header: '',
              render: (row) => (
                <TransferActions
                  row={row}
                  canDispatch={canDispatch}
                  canReceive={canReceive}
                  onReceive={() => setReceiving(row)}
                />
              ),
            },
          ]}
        />
      </Panel>
      {open ? <CreateModal branches={context.branches} onClose={() => setOpen(false)} /> : null}
      {receiving ? <ReceiveModal transfer={receiving} onClose={() => setReceiving(null)} /> : null}
    </div>
  )
}

function TransferActions({
  row,
  canDispatch,
  canReceive,
  onReceive,
}: {
  row: Transfer
  canDispatch: boolean
  canReceive: boolean
  onReceive: () => void
}) {
  const queryClient = useQueryClient()
  const run = useMutation({
    mutationFn: (action: 'approve' | 'dispatch') =>
      action === 'approve' ? approveTransfer(row.id) : dispatchTransfer(row.id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['transfers'] })
      void queryClient.invalidateQueries({ queryKey: ['balances'] })
    },
  })
  return (
    <div className="flex gap-2">
      {canDispatch && row.status === 'DRAFT' ? (
        <Button size="sm" variant="secondary" onClick={() => run.mutate('approve')}>Approve</Button>
      ) : null}
      {canDispatch && row.status === 'APPROVED' ? (
        <Button size="sm" onClick={() => run.mutate('dispatch')}>Dispatch</Button>
      ) : null}
      {canReceive && row.status === 'DISPATCHED' ? (
        <Button size="sm" onClick={onReceive}>Confirm receipt</Button>
      ) : null}
      {run.isError ? <p className="text-sm text-danger">{errorMessage(run.error)}</p> : null}
    </div>
  )
}

function CreateModal({
  branches,
  onClose,
}: {
  branches: Array<{ id: string; name: string }>
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const items = useQuery({ queryKey: ['items'], queryFn: listItems })
  const create = useMutation({
    mutationFn: createTransfer,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['transfers'] })
      onClose()
    },
  })
  const [branchId, setBranchId] = useState(branches[0]?.id ?? '')
  const [lines, setLines] = useState([{ item_id: '', quantity: '', unit: 'EACH' }])
  const catalog = items.data ?? []
  return (
    <Modal open title="New transfer" onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate({
            branch_id: branchId,
            lines: lines.map((line) => ({
              item_id: line.item_id || catalog[0]?.id || '',
              quantity: line.quantity,
              unit: line.unit,
            })),
          })
        }}
      >
        <label className="grid gap-1.5 text-sm">
          <span className="font-medium">Branch</span>
          <select className="h-11 rounded-xl border border-line bg-cream px-3" value={branchId} onChange={(event) => setBranchId(event.target.value)}>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>{branch.name}</option>
            ))}
          </select>
        </label>
        {lines.map((line, index) => (
          <div key={index} className="grid gap-2 rounded-2xl border border-line p-3">
            <label className="grid gap-1.5 text-sm">
              <span className="font-medium">Item</span>
              <select
                className="h-11 rounded-xl border border-line bg-cream px-3"
                value={line.item_id || catalog[0]?.id || ''}
                onChange={(event) =>
                  setLines((current) =>
                    current.map((row, rowIndex) =>
                      rowIndex === index ? { ...row, item_id: event.target.value } : row,
                    ),
                  )
                }
              >
                {catalog.map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>
            <TextField
              label="Quantity"
              required
              value={line.quantity}
              onChange={(event) =>
                setLines((current) =>
                  current.map((row, rowIndex) =>
                    rowIndex === index ? { ...row, quantity: event.target.value } : row,
                  ),
                )
              }
            />
            <label className="grid gap-1.5 text-sm">
              <span className="font-medium">Unit</span>
              <select
                className="h-11 rounded-xl border border-line bg-cream px-3"
                value={line.unit}
                onChange={(event) =>
                  setLines((current) =>
                    current.map((row, rowIndex) =>
                      rowIndex === index ? { ...row, unit: event.target.value } : row,
                    ),
                  )
                }
              >
                <option value="EACH">each</option>
                <option value="G">g</option>
                <option value="KG">kg</option>
                <option value="ML">ml</option>
                <option value="L">L</option>
              </select>
            </label>
          </div>
        ))}
        <Button
          type="button"
          variant="secondary"
          onClick={() => setLines((current) => [...current, { item_id: catalog[0]?.id ?? '', quantity: '', unit: 'EACH' }])}
        >
          Add line
        </Button>
        {create.isError ? <p className="text-sm text-danger">{errorMessage(create.error)}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={create.isPending}>Save draft</Button>
        </div>
      </form>
    </Modal>
  )
}

function ReceiveModal({ transfer, onClose }: { transfer: Transfer; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [rows, setRows] = useState(
    transfer.lines.map((line) => ({
      line_id: line.id,
      name: line.item_name,
      unit: line.unit,
      dispatched: line.dispatched_quantity,
      received_quantity: line.dispatched_quantity,
      note: '',
    })),
  )
  const receive = useMutation({
    mutationFn: () =>
      receiveTransfer(
        transfer.id,
        rows.map((row) => ({
          line_id: row.line_id,
          received_quantity: row.received_quantity,
          note: row.note,
        })),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['transfers'] })
      await queryClient.invalidateQueries({ queryKey: ['balances'] })
      onClose()
    },
  })
  return (
    <Modal open title={`Confirm ${transfer.number}`} onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          receive.mutate()
        }}
      >
        {rows.map((row, index) => (
          <div key={row.line_id} className="grid gap-2 rounded-2xl border border-line p-3">
            <p className="text-sm font-medium">
              {row.name} · dispatched {row.dispatched} {row.unit}
            </p>
            <TextField
              label="Received"
              required
              value={row.received_quantity}
              onChange={(event) =>
                setRows((current) =>
                  current.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, received_quantity: event.target.value } : item,
                  ),
                )
              }
            />
            <TextField
              label="Discrepancy note"
              value={row.note}
              onChange={(event) =>
                setRows((current) =>
                  current.map((item, itemIndex) =>
                    itemIndex === index ? { ...item, note: event.target.value } : item,
                  ),
                )
              }
            />
          </div>
        ))}
        {receive.isError ? <p className="text-sm text-danger">{errorMessage(receive.error)}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={receive.isPending}>Confirm</Button>
        </div>
      </form>
    </Modal>
  )
}
