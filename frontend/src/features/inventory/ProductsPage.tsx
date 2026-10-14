import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createProduct,
  listItems,
  listProducts,
  updateProduct,
  type ProductMaster,
} from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { SelectField, TextArea, TextField } from '../../shared/ui/Field.tsx'
import { ErrorState, NoAccess } from '../../shared/ui/Feedback.tsx'
import { PageHeader, Panel, StatusBadge } from '../../shared/ui/PageHeader.tsx'
import { useWorkspace } from '../workspace/queries.ts'
import { itemKinds, kindLabel, previewCode, stockUnits, unitLabel } from './catalogLabels.ts'
import { Pager, usePagedRows } from './listTools.tsx'
import { ImageField } from './ImageField.tsx'
import { ProductRecipe } from './ProductRecipe.tsx'

function formFromProduct(product: ProductMaster) {
  return {
    name: product.name,
    sku: product.sku,
    category: product.category,
    description: product.description ?? '',
    image_key: product.image_key ?? '',
    selling_price: product.selling_price,
    labour_cost: product.labour_cost ?? '0',
    overhead_cost: product.overhead_cost ?? '0',
    sale_unit: product.sale_unit,
    kind: product.kind,
    inventory_item_id: product.inventory_item ?? '',
    branch_ids: product.branch_ids,
    is_active: product.is_active,
  }
}

const emptyProduct = {
  name: '',
  sku: '',
  category: '',
  description: '',
  image_key: '',
  selling_price: '',
  labour_cost: '0',
  overhead_cost: '0',
  sale_unit: 'EACH',
  kind: 'FINISHED',
  inventory_item_id: '',
  branch_ids: [] as string[],
  is_active: true,
}

export function ProductsPage() {
  usePageTitle('Products')
  const workspace = useWorkspace()
  const context = workspace.data
  const products = useQuery({ queryKey: ['products'], queryFn: listProducts, enabled: Boolean(context) })
  const items = useQuery({ queryKey: ['items'], queryFn: listItems, enabled: Boolean(context) })
  const [editor, setEditor] = useState<ProductMaster | 'new' | null>(null)
  const [editing, setEditing] = useState(false)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [active, setActive] = useState('')
  const filtered = (products.data ?? []).filter((product) => {
    const haystack = `${product.name} ${product.sku}`.toLowerCase()
    if (query.trim() && !haystack.includes(query.trim().toLowerCase())) return false
    if (category.trim() && !(product.category || '').toLowerCase().includes(category.trim().toLowerCase())) return false
    if (active === 'active' && !product.is_active) return false
    if (active === 'inactive' && product.is_active) return false
    return true
  })
  const paged = usePagedRows(filtered, `${query}|${category}|${active}`)
  if (!context) return null
  if (!can(context.permissions, 'catalog.view')) return <NoAccess />
  const canManage = can(context.permissions, 'catalog.manage')
  const branches = context.branches

  if (editor) {
    return (
      <ProductModal
        key={editor === 'new' ? 'new' : editor.id}
        product={editor === 'new' ? null : editor}
        editing={editing || editor === 'new'}
        canEdit={canManage}
        items={items.data ?? []}
        codes={(products.data ?? []).map((row) => row.sku)}
        branches={branches}
        onEdit={() => setEditing(true)}
        onBack={() => setEditing(false)}
        onClose={() => { setEditor(null); setEditing(false) }}
        onSaved={(saved) => { setEditor(saved); setEditing(false) }}
      />
    )
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Products"
        description="What Central Kitchen makes and sells. Open a product to see its recipe and cost."
        action={canManage ? <Button onClick={() => { setEditing(true); setEditor('new') }}>New product</Button> : null}
      />
      <div className="grid gap-3 sm:grid-cols-3">
        <TextField label="Search" value={query} placeholder="Name or code" onChange={(event) => setQuery(event.target.value)} />
        <TextField label="Category" value={category} placeholder="Desserts" onChange={(event) => setCategory(event.target.value)} />
        <SelectField label="Status" value={active} onChange={(event) => setActive(event.target.value)}>
          <option value="">All</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </SelectField>
      </div>
      {products.isError ? <ErrorState error={products.error} onRetry={() => void products.refetch()} /> : (
        <Panel>
          <DataTable
            caption="Products"
            rows={paged.rows}
            rowKey={(product) => product.id}
            empty="No products yet."
            onRowClick={(product) => { setEditing(false); setEditor(product) }}
            columns={[
              {
                header: 'Image',
                render: (product) => product.image_url
                  ? <img src={product.image_url} alt="" className="h-10 w-10 rounded-lg object-cover" />
                  : <span className="text-ink-soft">—</span>,
              },
              { header: 'Product', render: (product) => <span className="font-medium">{product.name}<span className="mt-0.5 block text-xs text-ink-soft">{product.sku}</span></span> },
              { header: 'Category', render: (product) => product.category || '—' },
              { header: 'Selling price', render: (product) => product.selling_price },
              { header: 'Estimated cost', render: (product) => product.costing?.estimated_cost ?? '—' },
              { header: 'Gross margin', render: (product) => product.costing?.gross_margin == null ? '—' : `${product.costing.gross_margin}%` },
              { header: 'Recipe', render: (product) => product.costing?.recipe_status === 'CONFIRMED' ? `v${product.costing.recipe_version}` : product.costing?.recipe_status === 'DRAFT' ? 'Draft' : 'None' },
              { header: 'Status', render: (product) => <StatusBadge status={product.is_active ? 'active' : 'inactive'} /> },
              {
                header: 'Actions',
                render: (product) => (
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="secondary" onClick={(event) => { event.stopPropagation(); setEditing(false); setEditor(product) }}>View</Button>
                    {canManage ? <Button size="sm" variant="secondary" onClick={(event) => { event.stopPropagation(); setEditing(true); setEditor(product) }}>Edit</Button> : null}
                    {canManage && product.is_active ? (
                      <Button size="sm" variant="secondary" onClick={(event) => {
                        event.stopPropagation()
                        if (!window.confirm(`Deactivate ${product.name}? The recipe and stock history stay.`)) return
                        void updateProduct(product.id, { is_active: false }).then(() => products.refetch())
                      }}>Deactivate</Button>
                    ) : null}
                  </div>
                ),
              },
            ]}
          />
          <Pager page={paged.page} pages={paged.pages} onPage={paged.setPage} />
        </Panel>
      )}
    </div>
  )
}

function ProductModal({
  product,
  editing,
  canEdit,
  items,
  codes,
  branches,
  onEdit,
  onBack,
  onClose,
  onSaved,
}: {
  product: ProductMaster | null
  editing: boolean
  canEdit: boolean
  items: Array<{ id: string; name: string; sku: string }>
  codes: string[]
  branches: Array<{ id: string; name: string }>
  onEdit: () => void
  onBack: () => void
  onClose: () => void
  onSaved: (product: ProductMaster) => void
}) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState(() => (product ? formFromProduct(product) : emptyProduct))
  const suggested = previewCode(form.name, codes, product?.sku ?? '')
  const save = useMutation({
    mutationFn: () => {
      const { sku: _sku, ...rest } = form
      const input = {
        ...rest,
        inventory_item_id: form.inventory_item_id || null,
      }
      return product ? updateProduct(product.id, input) : createProduct(input)
    },
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: ['products'] })
      onSaved(saved)
    },
  })
  function set<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const locked = Boolean(product) && !editing
  const codeValue = product ? product.sku : suggested
  return (
    <div className="grid gap-6">
      <PageHeader
        title={product ? product.name : 'New product'}
        description="What you sell, the price, and where it is available."
        action={
          <button type="button" className="text-sm text-ink-soft underline-offset-2 hover:underline" onClick={onClose}>
            Back to products
          </button>
        }
      />
      {product ? (
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={product.is_active ? 'active' : 'inactive'} />
          <span className="text-sm text-ink-soft">{product.sku} · {kindLabel(product.kind)}</span>
        </div>
      ) : null}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.8fr)]">
        <Panel>
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-display text-2xl tracking-tight">Details</h2>
            {canEdit && product && !editing ? (
              <Button variant="secondary" onClick={onEdit}>Edit</Button>
            ) : null}
          </div>
          <form
            className="mt-5 grid gap-4 sm:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault()
              save.mutate()
            }}
          >
        <TextField
          label="Product name *"
          required
          disabled={locked}
          value={form.name}
          onChange={(event) => set('name', event.target.value)}
        />
        <TextField
          label="Product code"
          readOnly
          disabled
          value={codeValue}
          hint={product ? 'This code stays the same if you rename the product.' : 'Preview from the name. Pistachio kunafa becomes PIST-01. The server assigns the final code.'}
        />
        <TextField label="Category *" required disabled={locked} value={form.category} onChange={(event) => set('category', event.target.value)} />
        <TextField label="Selling price *" required disabled={locked} value={form.selling_price} onChange={(event) => set('selling_price', event.target.value)} />
        <SelectField label="Unit" disabled={locked} value={form.sale_unit} onChange={(event) => set('sale_unit', event.target.value)}>
          {stockUnits.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </SelectField>
        <SelectField label="Product type" disabled={locked} value={form.kind} onChange={(event) => set('kind', event.target.value)}>
          {itemKinds.filter(([value]) => value !== 'PACKAGING').map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </SelectField>
        <TextField label="Labour cost per unit" disabled={locked} inputMode="decimal" value={form.labour_cost} onChange={(event) => set('labour_cost', event.target.value)} hint="Optional. Not taken from stock." />
        <TextField label="Overhead cost per unit" disabled={locked} inputMode="decimal" value={form.overhead_cost} onChange={(event) => set('overhead_cost', event.target.value)} hint="Optional estimated overhead." />
        <div className="sm:col-span-2">
          <TextArea label="Description" disabled={locked} value={form.description} onChange={(event) => set('description', event.target.value)} />
        </div>
        <div className="sm:col-span-2">
          <ImageField
            purpose="product"
            imageUrl={product?.image_url ?? null}
            disabled={locked}
            onChange={(imageKey) => set('image_key', imageKey)}
          />
        </div>
        <div className="sm:col-span-2">
          <SelectField
            label="Inventory item"
            disabled={locked}
            hint="Optional. Leave this blank and a finished stock item is created with no quantity. Recipes use inventory items as ingredients."
            value={form.inventory_item_id}
            onChange={(event) => set('inventory_item_id', event.target.value)}
          >
            <option value="">Not linked yet</option>
            {items.map((item) => (
              <option key={item.id} value={item.id}>{item.name} ({item.sku})</option>
            ))}
          </SelectField>
        </div>
        <fieldset className="grid gap-2 sm:col-span-2">
          <legend className="text-sm font-medium">Branch availability</legend>
          <p className="text-sm text-ink-soft">Leave every branch unchecked to sell this product at all branches.</p>
          {branches.length === 0 ? <p className="text-sm text-ink-soft">No branches yet.</p> : null}
          {branches.map((branch) => (
            <label key={branch.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                disabled={locked}
                checked={form.branch_ids.includes(branch.id)}
                onChange={(event) =>
                  set(
                    'branch_ids',
                    event.target.checked
                      ? [...form.branch_ids, branch.id]
                      : form.branch_ids.filter((id) => id !== branch.id),
                  )
                }
              />
              {branch.name}
            </label>
          ))}
        </fieldset>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" disabled={locked} checked={form.is_active} onChange={(event) => set('is_active', event.target.checked)} />
          Active
        </label>
        {save.isError ? <p className="text-sm text-danger sm:col-span-2">{errorMessage(save.error)}</p> : null}
        {editing ? (
          <div className="flex gap-2 sm:col-span-2">
            <Button type="submit" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save changes'}</Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                if (!product) {
                  onClose()
                  return
                }
                setForm(formFromProduct(product))
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
            <p className="mt-1 text-sm text-ink-soft">Estimated from the confirmed recipe. The actual cost is saved when a production batch is completed.</p>
            <dl className="mt-4 grid gap-3">
              <Fact label="Code" value={codeValue || '—'} />
              <Fact label="Price" value={form.selling_price || '—'} />
              <Fact label="Ingredient cost" value={product?.costing?.ingredient_cost ?? '—'} />
              <Fact label="Estimated production cost" value={product?.costing?.estimated_cost ?? '—'} />
              <Fact label="Gross profit" value={product?.costing?.gross_profit ?? '—'} />
              <Fact label="Gross margin" value={product?.costing?.gross_margin == null ? '—' : `${product.costing.gross_margin}%`} />
              <Fact label="Unit" value={unitLabel(form.sale_unit)} />
              <Fact label="Stock item" value={items.find((row) => row.id === form.inventory_item_id)?.name || 'Not linked'} />
              <Fact label="Branches" value={form.branch_ids.length === 0 ? 'All branches' : form.branch_ids.map((id) => branches.find((branch) => branch.id === id)?.name ?? 'Branch').join(', ')} />
            </dl>
          </Panel>
        </div>
      </div>
      {product ? <ProductRecipe product={product} canEdit={canEdit} /> : null}
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
