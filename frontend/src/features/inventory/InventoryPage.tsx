import { useState } from 'react'
import { Plus } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createItem, listItems, listLocations, updateItem, type ItemInput, type StockItem } from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { SelectField, TextField } from '../../shared/ui/Field.tsx'
import { ErrorState } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { Panel } from '../../shared/ui/PageHeader.tsx'
import { useWorkspace } from '../workspace/queries.ts'
import { costingMethods, defaultPurchaseFactor, expiryLabel, kindLabel, stockUnits, unitLabel } from './catalogLabels.ts'
import { Pager, usePagedRows } from './listTools.tsx'

const emptyItem = {
  name: '',
  sku: '',
  category: 'Raw Materials',
  kind: 'RAW',
  stock_unit: 'KG',
  purchase_unit: 'KG',
  purchase_factor: '1',
  supplier_name: '',
  costing_method: 'MOVING_AVERAGE',
  standard_cost: '0',
  minimum_stock: '0',
  storage_location_id: '',
  tracks_batch: false,
  tracks_expiry: false,
  expiry_date: '',
  tracks_stock: true,
  is_active: true,
}

const kindChoices = [
  ['RAW', 'Ingredient (sugar, flour, nuts…)'],
  ['PACKAGING', 'Packaging (boxes, bags, cups…)'],
  ['SEMI', 'Half-made (used to make other items)'],
  ['FINISHED', 'Ready to sell'],
] as const

export function InventoryPage() {
  const workspace = useWorkspace()
  const context = workspace.data
  const items = useQuery({
    queryKey: ['items'],
    queryFn: listItems,
    enabled: Boolean(context && can(context.permissions, 'catalog.view')),
  })
  const [editor, setEditor] = useState<StockItem | 'new' | null>(null)
  const [editing, setEditing] = useState(false)
  const [query, setQuery] = useState('')
  const filtered = (items.data ?? []).filter((item) => {
    const haystack = `${item.name} ${item.sku} ${item.category} ${kindLabel(item.kind)}`.toLowerCase()
    return haystack.includes(query.trim().toLowerCase())
  })
  const paged = usePagedRows(filtered, query)
  if (!context) return null
  const canManage = can(context.permissions, 'catalog.manage')

  return (
    <div className="grid gap-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Items</h2>
          <p className="text-sm text-ink-soft">Step 1: list everything you buy, make, or sell. Click an item to edit it.</p>
        </div>
        {canManage ? (
          <Button onClick={() => { setEditing(true); setEditor('new') }}>
            <Plus className="h-4 w-4" />
            Add item
          </Button>
        ) : null}
      </div>
      <label className="grid max-w-sm gap-1.5 text-sm">
        <span className="sr-only">Search</span>
        <input
          className="h-11 rounded-xl border border-line bg-cream px-3"
          value={query}
          placeholder="Search by name"
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>
      {items.isError ? <ErrorState error={items.error} onRetry={() => void items.refetch()} /> : (
        <Panel>
          <DataTable
            caption="Items"
            rows={paged.rows}
            rowKey={(item) => item.id}
            empty={query ? 'No items match that search.' : 'No items yet. Click “Add item” to create your first one, like Sugar or Boxes.'}
            onRowClick={(item) => { setEditing(false); setEditor(item) }}
            columns={[
              { header: 'Item', render: (item) => <span className="font-medium">{item.name}</span> },
              { header: 'Code', render: (item) => item.sku },
              { header: 'Kind', render: (item) => kindLabel(item.kind) },
              { header: 'Counted in', render: (item) => unitLabel(item.stock_unit || item.base_unit) },
              {
                header: 'Warn below',
                render: (item) =>
                  Number(item.minimum_stock) > 0 ? `${item.minimum_stock} ${unitLabel(item.stock_unit || item.base_unit)}` : '—',
              },
              { header: 'Expires', render: (item) => expiryLabel(item.expiry_date) },
              { header: 'Status', render: (item) => (item.is_active ? 'In use' : 'Not in use') },
            ]}
          />
          <Pager page={paged.page} pages={paged.pages} onPage={paged.setPage} />
        </Panel>
      )}
      {editor ? (
        <ItemModal
          key={editor === 'new' ? 'new' : editor.id}
          item={editor === 'new' ? null : editor}
          editing={editing || editor === 'new'}
          canEdit={canManage}
          onEdit={() => setEditing(true)}
          onBack={() => setEditing(false)}
          onClose={() => setEditor(null)}
          onSaved={(saved) => { setEditor(saved); setEditing(false) }}
        />
      ) : null}
    </div>
  )
}

function ItemModal({
  item,
  editing,
  canEdit,
  onEdit,
  onBack,
  onClose,
  onSaved,
}: {
  item: StockItem | null
  editing: boolean
  canEdit: boolean
  onEdit: () => void
  onBack: () => void
  onClose: () => void
  onSaved: (item: StockItem) => void
}) {
  const queryClient = useQueryClient()
  const locations = useQuery({ queryKey: ['locations'], queryFn: listLocations })
  const places = (locations.data ?? []).filter((location) => location.kind !== 'IN_TRANSIT')
  const [form, setForm] = useState(() =>
    item
      ? {
          name: item.name,
          sku: item.sku,
          category: item.category,
          kind: item.kind,
          stock_unit: item.stock_unit || item.base_unit,
          purchase_unit: item.purchase_unit || item.stock_unit || item.base_unit,
          purchase_factor: item.purchase_factor || '1',
          supplier_name: item.supplier_name,
          costing_method: item.costing_method || 'MOVING_AVERAGE',
          standard_cost: item.standard_cost,
          minimum_stock: item.minimum_stock,
          storage_location_id: item.storage_location ?? '',
          tracks_batch: item.tracks_batch,
          tracks_expiry: item.tracks_expiry,
          expiry_date: item.expiry_date ?? '',
          tracks_stock: item.tracks_stock,
          is_active: item.is_active,
        }
      : emptyItem,
  )
  const save = useMutation({
    mutationFn: (input: ItemInput) => (item ? updateItem(item.id, input) : createItem(input)),
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: ['items'] })
      onSaved(saved)
    },
  })
  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }
  const unit = unitLabel(form.stock_unit)
  if (item && !editing) {
    return (
      <Modal open title={item.name} onClose={onClose}>
        <dl className="grid gap-3 sm:grid-cols-2">
          <Fact label="Item code" value={item.sku} />
          <Fact label="Kind" value={kindLabel(item.kind)} />
          <Fact label="Counted in" value={unitLabel(item.stock_unit || item.base_unit)} />
          <Fact label="Warn below" value={Number(item.minimum_stock) > 0 ? `${item.minimum_stock} ${unitLabel(item.stock_unit || item.base_unit)}` : '—'} />
          <Fact label="Expires" value={item.tracks_expiry ? expiryLabel(item.expiry_date) : 'Does not expire'} />
          <Fact label="Group" value={item.category || '—'} />
          <Fact label="Supplier" value={item.supplier_name || '—'} />
          <Fact label="Status" value={item.is_active ? 'In use' : 'Not in use'} />
        </dl>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Close</Button>
          {canEdit ? <Button onClick={onEdit}>Edit</Button> : null}
        </div>
      </Modal>
    )
  }
  return (
    <Modal open title={item ? 'Edit item' : 'Add an item'} onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          const payload: ItemInput = {
            ...form,
            storage_location_id: form.storage_location_id || null,
            expiry_date: form.tracks_expiry && form.expiry_date ? form.expiry_date : null,
          }
          delete payload.sku
          save.mutate(payload)
        }}
      >
        <TextField
          label="Item code"
          value={item?.sku || 'Assigned when you save'}
          disabled
          hint="Created automatically, like ITM-0001. This cannot be changed."
        />
        <TextField
          label="1. Item name"
          required
          autoFocus
          placeholder="Example: Sugar"
          value={form.name}
          onChange={(event) => set('name', event.target.value)}
        />
        <SelectField label="2. What kind of item is it?" value={form.kind} onChange={(event) => set('kind', event.target.value)}>
          {kindChoices.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </SelectField>
        <SelectField
          label="3. How do you count it?"
          value={form.stock_unit}
          hint="Pick the unit you use in the kitchen."
          onChange={(event) => {
            const stock_unit = event.target.value
            setForm((current) => {
              const purchase_unit = item ? current.purchase_unit : stock_unit
              return {
                ...current,
                stock_unit,
                purchase_unit,
                purchase_factor: defaultPurchaseFactor(purchase_unit, stock_unit),
              }
            })
          }}
        >
          {stockUnits.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </SelectField>
        <TextField
          label={`4. Warn me when stock is below (${unit})`}
          inputMode="decimal"
          value={form.minimum_stock}
          hint="Optional. Leave 0 if you don't want a warning."
          onChange={(event) => set('minimum_stock', event.target.value)}
        />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.tracks_expiry}
            onChange={(event) => {
              const tracks_expiry = event.target.checked
              setForm((current) => ({ ...current, tracks_expiry, expiry_date: tracks_expiry ? current.expiry_date : '' }))
            }}
          />
          This item expires
        </label>
        {form.tracks_expiry ? (
          <TextField
            label="Expires on"
            type="date"
            required
            value={form.expiry_date}
            hint="The date the whole stock of this item should be used by."
            onChange={(event) => set('expiry_date', event.target.value)}
          />
        ) : null}

        <details className="rounded-xl border border-line px-3 py-2">
          <summary className="cursor-pointer text-sm font-medium">More options (optional)</summary>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <TextField label="Group" value={form.category} hint="Example: Dairy, Nuts" onChange={(event) => set('category', event.target.value)} />
            <TextField label={`Cost per ${unit}`} inputMode="decimal" value={form.standard_cost} onChange={(event) => set('standard_cost', event.target.value)} />
            <TextField label="Supplier" value={form.supplier_name} onChange={(event) => set('supplier_name', event.target.value)} />
            <SelectField
              label="You buy it in"
              value={form.purchase_unit}
              onChange={(event) => {
                const purchase_unit = event.target.value
                setForm((current) => ({
                  ...current,
                  purchase_unit,
                  purchase_factor: defaultPurchaseFactor(purchase_unit, current.stock_unit),
                }))
              }}
            >
              {stockUnits.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </SelectField>
            <TextField
              label={`1 ${unitLabel(form.purchase_unit)} = how many ${unit}?`}
              inputMode="decimal"
              value={form.purchase_factor}
              onChange={(event) => set('purchase_factor', event.target.value)}
            />
            <SelectField label="Where is it stored?" value={form.storage_location_id} onChange={(event) => set('storage_location_id', event.target.value)}>
              <option value="">Not set</option>
              {places.map((location) => (
                <option key={location.id} value={location.id}>{location.name}</option>
              ))}
            </SelectField>
            <SelectField label="Cost method" value={form.costing_method} onChange={(event) => set('costing_method', event.target.value)}>
              {costingMethods.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </SelectField>
            <div className="grid gap-2 sm:col-span-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.tracks_batch} onChange={(event) => set('tracks_batch', event.target.checked)} />
                It comes in batches
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.tracks_stock} onChange={(event) => set('tracks_stock', event.target.checked)} />
                Count how much I have
              </label>
              {item ? (
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={form.is_active} onChange={(event) => set('is_active', event.target.checked)} />
                  Item is in use
                </label>
              ) : null}
            </div>
          </div>
        </details>

        {save.isError ? <p className="text-sm text-danger">{errorMessage(save.error)}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={item ? onBack : onClose}>Cancel</Button>
          <Button type="submit" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save item'}</Button>
        </div>
      </form>
    </Modal>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm text-ink-soft">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  )
}
