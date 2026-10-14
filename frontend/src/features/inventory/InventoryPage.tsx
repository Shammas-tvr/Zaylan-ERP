import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createItem,
  createSupplier,
  listItemsAt,
  listLocations,
  listSuppliers,
  updateItem,
  type ItemInput,
  type StockItem,
} from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { SelectField, TextField } from '../../shared/ui/Field.tsx'
import { ErrorState } from '../../shared/ui/Feedback.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'
import { useSession, useWorkspace } from '../workspace/queries.ts'
import { costingMethods, itemKinds, kindLabel, previewCode, stockStatuses, stockUnits, unitLabel } from './catalogLabels.ts'
import { ImageField } from './ImageField.tsx'
import { Pager, usePagedRows } from './listTools.tsx'

type PolicyForm = { location_id: string; minimum_quantity: string }

type ItemForm = {
  name: string
  kind: string
  stock_unit: string
  standard_cost: string
  costing_method: string
  image_key: string
  default_supplier_id: string
  supplier_ids: string[]
  policies: PolicyForm[]
  is_active: boolean
}

function formFromItem(item: StockItem): ItemForm {
  return {
    name: item.name,
    kind: item.kind,
    stock_unit: item.stock_unit || item.base_unit,
    standard_cost: item.standard_cost,
    costing_method: item.costing_method || 'MOVING_AVERAGE',
    image_key: item.image_key ?? '',
    default_supplier_id: item.default_supplier ?? '',
    supplier_ids: item.supplier_ids ?? [],
    policies: (item.stock_policies ?? []).map((row) => ({
      location_id: row.location,
      minimum_quantity: row.minimum_quantity,
    })),
    is_active: item.is_active,
  }
}

const emptyItem: ItemForm = {
  name: '',
  kind: 'RAW',
  stock_unit: 'KG',
  standard_cost: '0',
  costing_method: 'MOVING_AVERAGE',
  image_key: '',
  default_supplier_id: '',
  supplier_ids: [],
  policies: [],
  is_active: true,
}

function payload(form: ItemForm): ItemInput {
  return {
    name: form.name.trim(),
    kind: form.kind,
    stock_unit: form.stock_unit,
    standard_cost: form.standard_cost || '0',
    costing_method: form.costing_method,
    image_key: form.image_key,
    default_supplier_id: form.default_supplier_id || null,
    supplier_ids: form.supplier_ids,
    stock_policies: form.policies,
    tracks_stock: true,
    is_active: form.is_active,
  }
}

export function InventoryPage() {
  const workspace = useWorkspace()
  const session = useSession()
  const context = workspace.data
  const queryClient = useQueryClient()
  const locations = useQuery({ queryKey: ['locations'], queryFn: listLocations, enabled: Boolean(context) })
  const places = (locations.data ?? []).filter((location) => location.kind !== 'IN_TRANSIT')
  const [locationId, setLocationId] = useState('')
  const [editor, setEditor] = useState<StockItem | 'new' | null>(null)
  const [editing, setEditing] = useState(false)
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState('')
  const [status, setStatus] = useState('')
  const [notice, setNotice] = useState('')
  const items = useQuery({
    queryKey: ['items', locationId],
    queryFn: () => listItemsAt(locationId),
    enabled: Boolean(context && locationId && can(context.permissions, 'catalog.view')),
  })
  const deactivate = useMutation({
    mutationFn: (id: string) => updateItem(id, { is_active: false }),
    onSuccess: async () => {
      setNotice('Item deactivated. Past stock movements are unchanged.')
      await queryClient.invalidateQueries({ queryKey: ['items'] })
    },
  })

  useEffect(() => {
    if (locationId || places.length === 0) return
    const match = places.find((location) => location.branch && location.branch === session.branchId)
    setLocationId((match ?? places[0]).id)
  }, [places, locationId, session.branchId])

  if (!context) return null
  const canManage = can(context.permissions, 'catalog.manage')
  const currency = context.organization.currency || ''
  const filtered = (items.data ?? []).filter((item) => {
    const haystack = `${item.name} ${item.sku}`.toLowerCase()
    if (query.trim() && !haystack.includes(query.trim().toLowerCase())) return false
    if (kind && item.kind !== kind) return false
    if (status && item.stock_status !== status) return false
    return true
  })
  const paged = usePagedRows(filtered, `${query}|${kind}|${status}|${locationId}`)

  if (editor) {
    return (
      <ItemFormPage
        key={editor === 'new' ? 'new' : editor.id}
        item={editor === 'new' ? null : editor}
        editing={editing || editor === 'new'}
        canEdit={canManage}
        currency={currency}
        codes={(items.data ?? []).map((row) => row.sku)}
        notice={notice}
        onEdit={() => setEditing(true)}
        onBack={() => setEditing(false)}
        onClose={() => { setEditor(null); setEditing(false) }}
        onSaved={(saved) => { setEditor(saved); setEditing(false); setNotice('Item saved. Stock quantity was not changed.') }}
      />
    )
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Items</h2>
          <p className="text-sm text-ink-soft">Stock for the selected branch. Creating an item does not add quantity.</p>
        </div>
        {canManage ? (
          <Button onClick={() => { setNotice(''); setEditing(true); setEditor('new') }}>
            <Plus className="h-4 w-4" />
            Add item
          </Button>
        ) : null}
      </div>
      {notice ? <p className="text-sm text-ink">{notice}</p> : null}
      {deactivate.isError ? <p className="text-sm text-danger">{errorMessage(deactivate.error)}</p> : null}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <TextField label="Search" value={query} placeholder="Name or code" onChange={(event) => setQuery(event.target.value)} />
        <SelectField label="Item type" value={kind} onChange={(event) => setKind(event.target.value)}>
          <option value="">All types</option>
          {itemKinds.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </SelectField>
        <SelectField label="Branch or location" value={locationId} onChange={(event) => setLocationId(event.target.value)}>
          {places.map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}
        </SelectField>
        <SelectField label="Stock status" value={status} onChange={(event) => setStatus(event.target.value)}>
          {stockStatuses.map(([value, label]) => <option key={value || 'all'} value={value}>{label}</option>)}
        </SelectField>
      </div>
      {!locationId ? <p className="text-sm text-ink-soft">Loading locations…</p> : items.isError ? <ErrorState error={items.error} onRetry={() => void items.refetch()} /> : (
        <Panel>
          {items.isLoading ? <p className="p-4 text-sm text-ink-soft">Loading items…</p> : (
            <DataTable
              caption="Items"
              rows={paged.rows}
              rowKey={(item) => item.id}
              empty={query || kind || status ? 'No items match these filters.' : 'No items yet. Add the first one, such as flour or boxes.'}
              onRowClick={(item) => { setNotice(''); setEditing(false); setEditor(item) }}
              columns={[
                {
                  header: 'Image',
                  render: (item) => item.image_url
                    ? <img src={item.image_url} alt="" className="h-10 w-10 rounded-lg object-cover" />
                    : <span className="text-ink-soft">—</span>,
                },
                { header: 'Item name', render: (item) => <span className="font-medium">{item.name}</span> },
                { header: 'Item code', render: (item) => item.sku },
                { header: 'Item type', render: (item) => kindLabel(item.kind) },
                { header: 'Current branch stock', render: (item) => item.branch_quantity ?? '—' },
                { header: 'Stock unit', render: (item) => unitLabel(item.stock_unit || item.base_unit) },
                {
                  header: 'Inventory cost',
                  render: (item) => `${item.standard_cost} ${currency}/${unitLabel(item.stock_unit || item.base_unit)}`.trim(),
                },
                { header: 'Minimum stock', render: (item) => item.branch_minimum ?? '—' },
                { header: 'Stock status', render: (item) => item.stock_status ? <StatusBadge status={item.stock_status} /> : '—' },
                {
                  header: 'Actions',
                  render: (item) => (
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="secondary" onClick={(event) => { event.stopPropagation(); setNotice(''); setEditing(false); setEditor(item) }}>View</Button>
                      {canManage ? <Button size="sm" variant="secondary" onClick={(event) => { event.stopPropagation(); setNotice(''); setEditing(true); setEditor(item) }}>Edit</Button> : null}
                      {canManage && item.is_active ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={deactivate.isPending}
                          onClick={(event) => {
                            event.stopPropagation()
                            if (!window.confirm(`Deactivate ${item.name}? Past movements stay as they are.`)) return
                            deactivate.mutate(item.id)
                          }}
                        >
                          Deactivate
                        </Button>
                      ) : null}
                    </div>
                  ),
                },
              ]}
            />
          )}
          <Pager page={paged.page} pages={paged.pages} onPage={paged.setPage} />
        </Panel>
      )}
    </div>
  )
}

function ItemFormPage({
  item,
  editing,
  canEdit,
  currency,
  codes,
  notice,
  onEdit,
  onBack,
  onClose,
  onSaved,
}: {
  item: StockItem | null
  editing: boolean
  canEdit: boolean
  currency: string
  codes: string[]
  notice: string
  onEdit: () => void
  onBack: () => void
  onClose: () => void
  onSaved: (item: StockItem) => void
}) {
  const queryClient = useQueryClient()
  const locations = useQuery({ queryKey: ['locations'], queryFn: listLocations })
  const suppliers = useQuery({ queryKey: ['suppliers'], queryFn: listSuppliers })
  const places = (locations.data ?? []).filter((location) => location.kind !== 'IN_TRANSIT')
  const [form, setForm] = useState<ItemForm>(() => (item ? formFromItem(item) : emptyItem))
  const [supplierName, setSupplierName] = useState('')
  const suggested = previewCode(form.name, codes, item?.sku ?? '')
  const codeValue = item ? item.sku : suggested
  const locked = Boolean(item) && !editing
  const save = useMutation({
    mutationFn: (input: ItemInput) => (item ? updateItem(item.id, input) : createItem(input)),
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: ['items'] })
      onSaved(saved)
    },
  })
  const addSupplier = useMutation({
    mutationFn: () => createSupplier(supplierName.trim()),
    onSuccess: async (supplier) => {
      await queryClient.invalidateQueries({ queryKey: ['suppliers'] })
      setForm((current) => ({
        ...current,
        default_supplier_id: current.default_supplier_id || supplier.id,
        supplier_ids: current.supplier_ids.includes(supplier.id) ? current.supplier_ids : [...current.supplier_ids, supplier.id],
      }))
      setSupplierName('')
    },
  })
  function set<K extends keyof ItemForm>(key: K, value: ItemForm[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }
  function togglePolicy(locationId: string, checked: boolean) {
    setForm((current) => ({
      ...current,
      policies: checked
        ? [...current.policies, { location_id: locationId, minimum_quantity: '0' }]
        : current.policies.filter((row) => row.location_id !== locationId),
    }))
  }
  const unit = unitLabel(form.stock_unit)
  const supplierLabel = suppliers.data?.find((row) => row.id === form.default_supplier_id)?.name || item?.default_supplier_name || '—'

  return (
    <div className="grid gap-6">
      <PageHeader
        title={item ? item.name : 'New item'}
        description="Item profile. Saving this does not add stock."
        action={
          <button type="button" className="text-sm text-ink-soft underline-offset-2 hover:underline" onClick={onClose}>
            Back to items
          </button>
        }
      />
      {item ? (
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={item.is_active ? 'active' : 'inactive'} />
          {item.stock_status ? <StatusBadge status={item.stock_status} /> : null}
          <span className="text-sm text-ink-soft">{item.sku} · {kindLabel(item.kind)}</span>
        </div>
      ) : null}
      {notice ? <p className="text-sm text-ink">{notice}</p> : null}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.8fr)]">
        <Panel>
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-display text-2xl tracking-tight">Details</h2>
            {canEdit && item && !editing ? <Button variant="secondary" onClick={onEdit}>Edit</Button> : null}
          </div>
          <form
            className="mt-5 grid gap-4 sm:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault()
              save.mutate(payload(form))
            }}
          >
            <h3 className="text-sm font-medium sm:col-span-2">Basic information</h3>
            <div className="sm:col-span-2">
              <ImageField
                purpose="item"
                imageUrl={item?.image_url ?? null}
                disabled={locked}
                onChange={(imageKey) => set('image_key', imageKey)}
              />
            </div>
            <TextField label="Item name *" required disabled={locked} value={form.name} placeholder="Pistachio kunafa" onChange={(event) => set('name', event.target.value)} />
            <TextField
              label="Item code"
              readOnly
              disabled
              value={codeValue}
              hint={item ? 'This code stays the same if you rename the item.' : 'Preview from the name. Pistachio kunafa becomes PIST-01. The server assigns the final code.'}
            />
            <SelectField label="Item type *" required disabled={locked} value={form.kind} onChange={(event) => set('kind', event.target.value)}>
              {itemKinds.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </SelectField>
            <SelectField label="Stock unit *" required disabled={locked} value={form.stock_unit} onChange={(event) => set('stock_unit', event.target.value)}>
              {stockUnits.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </SelectField>

            <h3 className="text-sm font-medium sm:col-span-2">Cost and valuation</h3>
            <TextField
              label={`Default cost per ${unit}${currency ? ` (${currency})` : ''}`}
              disabled={locked}
              inputMode="decimal"
              value={form.standard_cost}
              hint="A reference value. Record the real purchase cost when stock is received."
              onChange={(event) => set('standard_cost', event.target.value)}
            />
            <SelectField label="Cost method" disabled={locked} value={form.costing_method} onChange={(event) => set('costing_method', event.target.value)}>
              {costingMethods.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </SelectField>

            <h3 className="text-sm font-medium sm:col-span-2">Suppliers</h3>
            <SelectField label="Default supplier" disabled={locked} value={form.default_supplier_id} onChange={(event) => set('default_supplier_id', event.target.value)}>
              <option value="">None</option>
              {(suppliers.data ?? []).map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
            </SelectField>
            <div className="grid gap-2">
              <span className="text-sm font-medium">Also supplied by</span>
              <div className="grid gap-2">
                {(suppliers.data ?? []).filter((supplier) => supplier.id !== form.default_supplier_id).map((supplier) => (
                  <label key={supplier.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      disabled={locked}
                      checked={form.supplier_ids.includes(supplier.id)}
                      onChange={(event) => {
                        set('supplier_ids', event.target.checked
                          ? [...form.supplier_ids, supplier.id]
                          : form.supplier_ids.filter((id) => id !== supplier.id))
                      }}
                    />
                    {supplier.name}
                  </label>
                ))}
                {(suppliers.data ?? []).length === 0 ? <p className="text-sm text-ink-soft">No suppliers yet.</p> : null}
              </div>
            </div>
            {editing ? (
              <div className="flex flex-wrap items-end gap-2 sm:col-span-2">
                <div className="min-w-48 flex-1">
                  <TextField label="Add a supplier" value={supplierName} onChange={(event) => setSupplierName(event.target.value)} placeholder="Supplier name" />
                </div>
                <Button type="button" variant="secondary" disabled={!supplierName.trim() || addSupplier.isPending} onClick={() => addSupplier.mutate()}>
                  {addSupplier.isPending ? 'Adding…' : 'Add supplier'}
                </Button>
              </div>
            ) : null}
            {addSupplier.isError ? <p className="text-sm text-danger sm:col-span-2">{errorMessage(addSupplier.error)}</p> : null}

            <h3 className="text-sm font-medium sm:col-span-2">Where it is stocked</h3>
            <div className="grid gap-3 sm:col-span-2">
              <p className="text-sm text-ink-soft">Minimum stock is per location, in {unit}. Alerts apply only where this item is stocked.</p>
              {places.map((location) => {
                const policy = form.policies.find((row) => row.location_id === location.id)
                return (
                  <div key={location.id} className="grid gap-2 rounded-xl border border-line px-3 py-3 sm:grid-cols-[1fr_180px] sm:items-center">
                    <label className="flex items-center gap-2 text-sm">
                      <input type="checkbox" disabled={locked} checked={Boolean(policy)} onChange={(event) => togglePolicy(location.id, event.target.checked)} />
                      {location.name}
                    </label>
                    {policy ? (
                      <TextField
                        label={`Minimum (${unit})`}
                        disabled={locked}
                        inputMode="decimal"
                        value={policy.minimum_quantity}
                        onChange={(event) => {
                          const minimum_quantity = event.target.value
                          set('policies', form.policies.map((row) => row.location_id === location.id ? { ...row, minimum_quantity } : row))
                        }}
                      />
                    ) : <span className="text-sm text-ink-soft">Not stocked here</span>}
                  </div>
                )
              })}
            </div>

            {save.isError ? <p className="text-sm text-danger sm:col-span-2">{errorMessage(save.error)}</p> : null}
            {editing ? (
              <div className="flex gap-2 sm:col-span-2">
                <Button type="submit" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save changes'}</Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    if (!item) {
                      onClose()
                      return
                    }
                    setForm(formFromItem(item))
                    onBack()
                  }}
                >
                  Cancel
                </Button>
              </div>
            ) : null}
          </form>
        </Panel>
        <div className="grid content-start gap-6">
          <Panel>
            <h2 className="font-display text-2xl tracking-tight">At a glance</h2>
            <dl className="mt-4 grid gap-3">
              <Fact label="Code" value={codeValue || '—'} />
              <Fact label="Type" value={kindLabel(form.kind)} />
              <Fact label="Stock unit" value={unit} />
              <Fact label="Reference cost" value={`${form.standard_cost || '0'} ${currency}/${unit}`.trim()} />
              <Fact label="Cost method" value={form.costing_method === 'FIFO' ? 'FIFO' : 'Weighted average'} />
              <Fact label="Default supplier" value={supplierLabel} />
              <Fact label="Branch stock" value={item?.branch_quantity ?? '0'} />
              <Fact label="Minimum here" value={item?.branch_minimum ?? '—'} />
            </dl>
          </Panel>
        </div>
      </div>
    </div>
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
