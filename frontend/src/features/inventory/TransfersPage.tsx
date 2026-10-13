import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  approveTransfer,
  closeTransfer,
  createTransfer,
  dispatchTransfer,
  listItems,
  listLocations,
  listTransfers,
  receiveTransfer,
} from '../../shared/api/stock.ts'
import type { Transfer } from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { TextField } from '../../shared/ui/Field.tsx'
import { NoAccess } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'
import { useWorkspace } from '../workspace/queries.ts'
import { stockUnits } from './catalogLabels.ts'
import { Pager, usePagedRows } from './listTools.tsx'

export function TransfersPage() {
  const workspace = useWorkspace()
  const context = workspace.data
  const transfers = useQuery({ queryKey: ['transfers'], queryFn: listTransfers, enabled: Boolean(context) })
  const [open, setOpen] = useState(false)
  const [receiving, setReceiving] = useState<Transfer | null>(null)
  const [query, setQuery] = useState('')
  const [openOnly, setOpenOnly] = useState(true)
  const filtered = (transfers.data ?? []).filter((row) => {
    if (openOnly && row.status === 'CLOSED') return false
    const haystack = `${row.number} ${row.source_name || ''} ${row.destination_name}`.toLowerCase()
    return haystack.includes(query.trim().toLowerCase())
  })
  const paged = usePagedRows(filtered, `${query}|${openOnly}`)
  if (!context) return null
  if (!can(context.permissions, 'inventory.view')) return <NoAccess />
  const canDispatch = can(context.permissions, 'inventory.dispatch')
  const canReceive = can(context.permissions, 'inventory.receive')
  const canClose = can(context.permissions, 'inventory.adjust')
  const branches = context.branches

  return (
    <div className="grid gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Transfers</h2>
          <p className="text-sm text-ink-soft">Step 4: send stock from the kitchen to a branch. The branch confirms what arrived</p>
        </div>
        {canDispatch ? <Button onClick={() => setOpen(true)}>New transfer</Button> : null}
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <label className="grid min-w-56 gap-1.5 text-sm">
          <span className="font-medium">Search</span>
          <input
            className="h-11 rounded-xl border border-line bg-cream px-3"
            value={query}
            placeholder="Number or location"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" checked={openOnly} onChange={(event) => setOpenOnly(event.target.checked)} />
          Hide closed
        </label>
      </div>
      <Panel>
        <DataTable
          caption="Transfers"
          rows={paged.rows}
          rowKey={(row) => row.id}
          empty="No transfers yet."
          columns={[
            { header: 'Number', render: (row) => <span className="font-medium">{row.number}</span> },
            { header: 'From', render: (row) => row.source_name || '—' },
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
                  canClose={canClose}
                  onReceive={() => setReceiving(row)}
                />
              ),
            },
          ]}
        />
        <Pager page={paged.page} pages={paged.pages} onPage={paged.setPage} />
      </Panel>
      {open ? <TransferForm branches={branches} onClose={() => setOpen(false)} /> : null}
      {receiving ? <ReceiveModal transfer={receiving} onClose={() => setReceiving(null)} /> : null}
    </div>
  )
}

function TransferActions({
  row,
  canDispatch,
  canReceive,
  canClose,
  onReceive,
}: {
  row: Transfer
  canDispatch: boolean
  canReceive: boolean
  canClose: boolean
  onReceive: () => void
}) {
  const queryClient = useQueryClient()
  const [confirmDispatch, setConfirmDispatch] = useState(false)
  const run = useMutation({
    mutationFn: (action: 'approve' | 'dispatch' | 'close') => {
      if (action === 'approve') return approveTransfer(row.id)
      if (action === 'close') return closeTransfer(row.id)
      return dispatchTransfer(row.id)
    },
    onSuccess: () => {
      setConfirmDispatch(false)
      void queryClient.invalidateQueries({ queryKey: ['transfers'] })
      void queryClient.invalidateQueries({ queryKey: ['balances'] })
      void queryClient.invalidateQueries({ queryKey: ['movements'] })
    },
  })
  const canCloseNow = canClose && (row.status === 'RECEIVED' || row.status === 'PARTIALLY_RECEIVED')
  return (
    <div className="flex flex-wrap items-center gap-2">
      {canDispatch && row.status === 'DRAFT' ? (
        <Button size="sm" variant="secondary" onClick={() => run.mutate('approve')}>Approve</Button>
      ) : null}
      {canDispatch && row.status === 'APPROVED' && !confirmDispatch ? (
        <Button size="sm" onClick={() => setConfirmDispatch(true)}>Dispatch</Button>
      ) : null}
      {confirmDispatch ? (
        <>
          <span className="text-xs text-ink-soft">Move this stock into transit?</span>
          <Button size="sm" disabled={run.isPending} onClick={() => run.mutate('dispatch')}>Confirm</Button>
          <Button size="sm" variant="secondary" onClick={() => setConfirmDispatch(false)}>Cancel</Button>
        </>
      ) : null}
      {canReceive && row.status === 'DISPATCHED' ? (
        <Button size="sm" onClick={onReceive}>Confirm receipt</Button>
      ) : null}
      {canCloseNow ? (
        <Button size="sm" variant="secondary" disabled={run.isPending} onClick={() => run.mutate('close')}>Close</Button>
      ) : null}
      {run.isError ? <span className="text-xs text-danger">{errorMessage(run.error)}</span> : null}
    </div>
  )
}

function TransferForm({
  branches,
  onClose,
}: {
  branches: Array<{ id: string; name: string }>
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const items = useQuery({ queryKey: ['items'], queryFn: listItems })
  const locations = useQuery({ queryKey: ['locations'], queryFn: listLocations })
  const create = useMutation({
    mutationFn: createTransfer,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['transfers'] })
      onClose()
    },
  })
  const [branchId, setBranchId] = useState(branches[0]?.id ?? '')
  const [sourceId, setSourceId] = useState('')
  const [lines, setLines] = useState([{ item_id: '', quantity: '', unit: 'EACH' }])
  const catalog = (items.data ?? []).filter((item) => item.tracks_stock)
  const sources = (locations.data ?? []).filter(
    (location) => location.kind !== 'IN_TRANSIT' && location.branch !== branchId,
  )
  const selectedSource = sourceId || sources.find((location) => location.kind === 'CENTRAL_KITCHEN')?.id || sources[0]?.id || ''
  return (
    <Modal open title="New transfer" onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate({
            branch_id: branchId,
            source_location_id: selectedSource || undefined,
            lines: lines.map((line) => ({
              item_id: line.item_id || catalog[0]?.id || '',
              quantity: line.quantity,
              unit: line.unit,
            })),
          })
        }}
      >
        <label className="grid gap-1.5 text-sm">
          <span className="font-medium">From</span>
          <select className="h-11 rounded-xl border border-line bg-cream px-3" value={selectedSource} onChange={(event) => setSourceId(event.target.value)}>
            {sources.map((location) => (
              <option key={location.id} value={location.id}>{location.name}</option>
            ))}
          </select>
        </label>
        <label className="grid gap-1.5 text-sm">
          <span className="font-medium">To branch</span>
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
                {stockUnits.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
          </div>
        ))}
        <Button
          type="button"
          variant="secondary"
          onClick={() => setLines((current) => [...current, { item_id: '', quantity: '', unit: 'EACH' }])}
        >
          Add another item
        </Button>
        {create.isError ? <p className="text-sm text-danger">{errorMessage(create.error)}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={create.isPending || branches.length === 0}>Save draft</Button>
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
            <p className="text-xs text-ink-soft">Only the received quantity is added at the branch. Anything short stays in transit.</p>
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
