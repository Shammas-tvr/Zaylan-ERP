import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { adjustStock, listBalances, listItems, listLocations, listMovements } from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { SelectField, TextField } from '../../shared/ui/Field.tsx'
import { ErrorState, NoAccess } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { Panel } from '../../shared/ui/PageHeader.tsx'
import { useWorkspace } from '../workspace/queries.ts'
import { expiryLabel, itemKinds, stockFromBase, stockNumber, stockUnits, unitLabel } from './catalogLabels.ts'
import { Pager, usePagedRows } from './listTools.tsx'

const reasons = [
  ['', 'All reasons'],
  ['ADJUSTMENT', 'Physical correction'],
  ['WASTAGE', 'Wastage'],
  ['EXPIRY', 'Expired'],
  ['PRODUCTION_CONSUME', 'Production consumption'],
  ['PRODUCTION_OUTPUT', 'Production output'],
  ['PRODUCTION_WASTE', 'Production waste'],
  ['TRANSFER_OUT', 'Transfer dispatch'],
  ['TRANSFER_IN', 'Transfer receipt'],
  ['SALE', 'Sale'],
  ['SALE_REVERSAL', 'Sale reversal'],
] as const

const reasonLabel = Object.fromEntries(reasons.filter(([value]) => value).map(([value, label]) => [value, label]))

export function StockPage() {
  const workspace = useWorkspace()
  const context = workspace.data
  const [locationId, setLocationId] = useState('')
  const [category, setCategory] = useState('')
  const [kind, setKind] = useState('')
  const [lowOnly, setLowOnly] = useState(false)
  const [reason, setReason] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [adjustOpen, setAdjustOpen] = useState(false)
  const locations = useQuery({ queryKey: ['locations'], queryFn: listLocations, enabled: Boolean(context) })
  const balances = useQuery({ queryKey: ['balances'], queryFn: listBalances, enabled: Boolean(context) })
  const movements = useQuery({
    queryKey: ['movements', locationId, reason, kind, category, from, to],
    queryFn: () => listMovements({ location: locationId, reason, kind, category, from, to }),
    enabled: Boolean(context),
  })
  const rows = (balances.data ?? []).filter((row) => {
    if (locationId && row.location !== locationId) return false
    if (kind && row.item_kind !== kind) return false
    if (category && !row.category.toLowerCase().includes(category.trim().toLowerCase())) return false
    if (lowOnly && !isLow(row)) return false
    return true
  })
  const paged = usePagedRows(rows, `${locationId}|${category}|${kind}|${lowOnly}`)
  if (!context) return null
  if (!can(context.permissions, 'inventory.view')) return <NoAccess />
  const canAdjust = can(context.permissions, 'inventory.adjust')

  return (
    <div className="grid gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Stock</h2>
          <p className="text-sm text-ink-soft">See how much you have in each place. Use “Adjust stock” to fix a count, wastage, or expiry</p>
        </div>
        {canAdjust ? <Button onClick={() => setAdjustOpen(true)}>Adjust stock</Button> : null}
      </div>
      <Panel>
        <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
          <SelectField label="Location" value={locationId} onChange={(event) => setLocationId(event.target.value)}>
            <option value="">All locations</option>
            {(locations.data ?? []).map((location) => (
              <option key={location.id} value={location.id}>{location.name}</option>
            ))}
          </SelectField>
          <TextField label="Category" value={category} onChange={(event) => setCategory(event.target.value)} placeholder="Raw Materials" />
          <SelectField label="Item type" value={kind} onChange={(event) => setKind(event.target.value)}>
            <option value="">All types</option>
            {itemKinds.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </SelectField>
          <label className="flex items-end gap-2 pb-2 text-sm">
            <input type="checkbox" checked={lowOnly} onChange={(event) => setLowOnly(event.target.checked)} />
            Low stock only
          </label>
        </div>
      </Panel>
      {balances.isError ? <ErrorState error={balances.error} onRetry={() => void balances.refetch()} /> : (
        <Panel>
          <DataTable
            caption="Stock on hand"
            rows={paged.rows}
            rowKey={(row) => row.id}
            empty={lowOnly ? 'Nothing is at or below its minimum.' : 'No stock yet. Record an adjustment to set an opening quantity.'}
            columns={[
              { header: 'Item', render: (row) => <span className="font-medium">{row.item_name}</span> },
              { header: 'SKU', render: (row) => row.item_sku },
              { header: 'Location', render: (row) => row.location_name },
              { header: 'On hand', render: (row) => `${stockFromBase(row.quantity, row.stock_unit || row.base_unit)} ${unitLabel(row.stock_unit || row.base_unit)}` },
              { header: 'Minimum', render: (row) => `${row.minimum_stock} ${unitLabel(row.stock_unit || row.base_unit)}` },
              { header: 'Expires', render: (row) => expiryLabel(row.expiry_date) },
              { header: 'Status', render: (row) => (isLow(row) ? 'Low' : 'OK') },
            ]}
          />
          <Pager page={paged.page} pages={paged.pages} onPage={paged.setPage} />
        </Panel>
      )}
      <div>
        <h3 className="text-lg font-semibold">Recent movements</h3>
        <p className="text-sm text-ink-soft">The audit trail for this filter</p>
      </div>
      <Panel>
        <div className="grid gap-3 p-4 sm:grid-cols-3">
          <SelectField label="Reason" value={reason} onChange={(event) => setReason(event.target.value)}>
            {reasons.map(([value, label]) => (
              <option key={value || 'all'} value={value}>{label}</option>
            ))}
          </SelectField>
          <TextField label="From" type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
          <TextField label="To" type="date" value={to} onChange={(event) => setTo(event.target.value)} />
        </div>
        {movements.isError ? <ErrorState error={movements.error} onRetry={() => void movements.refetch()} /> : (
          <DataTable
            caption="Movements"
            rows={movements.data ?? []}
            rowKey={(row) => row.id}
            empty="No movements for this filter."
            columns={[
              { header: 'When', render: (row) => new Date(row.created_at).toLocaleString() },
              { header: 'Item', render: (row) => `${row.item_name} (${row.item_sku})` },
              { header: 'Location', render: (row) => row.location_name },
              {
                header: 'Change',
                render: (row) => {
                  const amount = stockFromBase(row.quantity, row.stock_unit || row.base_unit)
                  return `${amount} ${unitLabel(row.stock_unit || row.base_unit)}`
                },
              },
              { header: 'Reason', render: (row) => reasonLabel[row.reason] || row.reason },
              { header: 'Note', render: (row) => row.note || '—' },
            ]}
          />
        )}
      </Panel>
      {adjustOpen ? <AdjustModal onClose={() => setAdjustOpen(false)} /> : null}
    </div>
  )
}

function isLow(row: { quantity: string; stock_unit: string; base_unit: string; minimum_stock: string }) {
  const minimum = Number(row.minimum_stock)
  if (!Number.isFinite(minimum) || minimum <= 0) return false
  return stockNumber(row.quantity, row.stock_unit || row.base_unit) <= minimum
}

function AdjustModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const locations = useQuery({ queryKey: ['locations'], queryFn: listLocations })
  const items = useQuery({ queryKey: ['items'], queryFn: listItems })
  const places = (locations.data ?? []).filter((location) => location.kind !== 'IN_TRANSIT')
  const catalog = (items.data ?? []).filter((item) => item.tracks_stock && item.is_active)
  const [locationId, setLocationId] = useState('')
  const [itemId, setItemId] = useState('')
  const [quantity, setQuantity] = useState('')
  const [unit, setUnit] = useState('')
  const [direction, setDirection] = useState<'in' | 'out'>('in')
  const [reason, setReason] = useState<'ADJUSTMENT' | 'WASTAGE' | 'EXPIRY'>('ADJUSTMENT')
  const [note, setNote] = useState('')
  const [confirming, setConfirming] = useState(false)
  const save = useMutation({
    mutationFn: adjustStock,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['balances'] })
      await queryClient.invalidateQueries({ queryKey: ['movements'] })
      onClose()
    },
  })
  const selectedLocation = locationId || places[0]?.id || ''
  const selectedItem = itemId || catalog[0]?.id || ''
  const selected = catalog.find((item) => item.id === selectedItem)
  const quantityUnit = unit || selected?.stock_unit || selected?.base_unit || 'G'
  const loss = reason === 'WASTAGE' || reason === 'EXPIRY'
  const movementDirection = loss ? 'out' : direction
  const payload = {
    location_id: selectedLocation,
    item_id: selectedItem,
    quantity,
    unit: quantityUnit,
    direction: movementDirection,
    reason,
    note: note.trim(),
  }
  return (
    <Modal open title={confirming ? 'Confirm stock movement' : 'Adjust stock'} onClose={onClose}>
      {confirming ? (
        <div className="grid gap-4">
          <p className="text-sm text-ink-soft">
            This writes a {reasonLabel[reason]?.toLowerCase() || 'stock'} movement for {quantity} {unitLabel(quantityUnit)}. The quantity on hand is updated from that movement and cannot be typed over afterwards.
          </p>
          {save.isError ? <p className="text-sm text-danger">{errorMessage(save.error)}</p> : null}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirming(false)}>Back</Button>
            <Button disabled={save.isPending} onClick={() => save.mutate(payload)}>
              {save.isPending ? 'Saving…' : 'Record movement'}
            </Button>
          </div>
        </div>
      ) : (
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (!note.trim()) return
            setConfirming(true)
          }}
        >
          {catalog.length === 0 ? (
            <p className="text-sm text-ink-soft">Create an inventory item with stock tracking turned on before recording a quantity.</p>
          ) : (
            <>
              <SelectField label="Location" value={selectedLocation} onChange={(event) => setLocationId(event.target.value)}>
                {places.map((location) => (
                  <option key={location.id} value={location.id}>{location.name}</option>
                ))}
              </SelectField>
              <SelectField
                label="Item"
                value={selectedItem}
                onChange={(event) => {
                  const next = catalog.find((item) => item.id === event.target.value)
                  setItemId(event.target.value)
                  if (next) setUnit(next.stock_unit || next.base_unit)
                }}
              >
                {catalog.map((item) => (
                  <option key={item.id} value={item.id}>{item.name} ({item.sku})</option>
                ))}
              </SelectField>
              <TextField label="Quantity" required value={quantity} onChange={(event) => setQuantity(event.target.value)} />
              <SelectField label="Unit" value={quantityUnit} onChange={(event) => setUnit(event.target.value)}>
                {stockUnits.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </SelectField>
              <SelectField
                label="Reason"
                value={reason}
                onChange={(event) => setReason(event.target.value as typeof reason)}
              >
                <option value="ADJUSTMENT">Physical correction or opening stock</option>
                <option value="WASTAGE">Wastage</option>
                <option value="EXPIRY">Expired items</option>
              </SelectField>
              {loss ? (
                <p className="text-sm text-ink-soft">Wastage and expiry always remove stock.</p>
              ) : (
                <SelectField label="Direction" value={direction} onChange={(event) => setDirection(event.target.value as 'in' | 'out')}>
                  <option value="in">Add stock</option>
                  <option value="out">Remove stock</option>
                </SelectField>
              )}
              <TextField label="Note" required value={note} onChange={(event) => setNote(event.target.value)} hint="Say what was counted, wasted, or expired." />
            </>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={catalog.length === 0 || !quantity || !note.trim()}>Review</Button>
          </div>
        </form>
      )}
    </Modal>
  )
}
