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
import { SelectField, TextField } from '../../shared/ui/Field.tsx'
import { ErrorState, NoAccess } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel } from '../../shared/ui/PageHeader.tsx'
import { useWorkspace } from '../workspace/queries.ts'
import { itemKinds, kindLabel, stockUnits, unitLabel } from './catalogLabels.ts'

const emptyProduct = {
  name: '',
  category: '',
  selling_price: '',
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
  if (!context) return null
  if (!can(context.permissions, 'catalog.view')) return <NoAccess />
  const canManage = can(context.permissions, 'catalog.manage')
  const branches = context.branches

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Products"
        description="What you sell. Open a product to see its details, then choose Edit to change it."
        action={canManage ? <Button onClick={() => { setEditing(true); setEditor('new') }}>New product</Button> : null}
      />
      {products.isError ? <ErrorState error={products.error} onRetry={() => void products.refetch()} /> : (
        <Panel>
          <DataTable
            caption="Product master"
            rows={products.data ?? []}
            rowKey={(product) => product.id}
            empty="No products yet."
            onRowClick={(product) => { setEditing(false); setEditor(product) }}
            columns={[
              { header: 'Product', render: (product) => <span className="font-medium">{product.name}</span> },
              { header: 'Code', render: (product) => product.sku },
              { header: 'Category', render: (product) => product.category || '—' },
              { header: 'Price', render: (product) => product.selling_price },
              { header: 'Unit', render: (product) => unitLabel(product.sale_unit) },
              { header: 'Type', render: (product) => kindLabel(product.kind) },
              { header: 'Stock item', render: (product) => product.inventory_item_name || '—' },
              {
                header: 'Branches',
                render: (product) => branchNames(product, branches),
              },
              { header: 'Status', render: (product) => (product.is_active ? 'Active' : 'Inactive') },
            ]}
          />
        </Panel>
      )}
      {editor ? (
        <ProductModal
          key={editor === 'new' ? 'new' : editor.id}
          product={editor === 'new' ? null : editor}
          editing={editing || editor === 'new'}
          canEdit={canManage}
          items={items.data ?? []}
          branches={branches}
          onEdit={() => setEditing(true)}
          onBack={() => setEditing(false)}
          onClose={() => setEditor(null)}
          onSaved={(saved) => { setEditor(saved); setEditing(false) }}
        />
      ) : null}
    </div>
  )
}

function branchNames(product: ProductMaster, branches: Array<{ id: string; name: string }>) {
  if (product.branch_ids.length === 0) return 'All branches'
  return product.branch_ids.map((id) => branches.find((branch) => branch.id === id)?.name ?? 'Branch').join(', ')
}

function ProductModal({
  product,
  editing,
  canEdit,
  items,
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
  branches: Array<{ id: string; name: string }>
  onEdit: () => void
  onBack: () => void
  onClose: () => void
  onSaved: (product: ProductMaster) => void
}) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState(() =>
    product
      ? {
          name: product.name,
          category: product.category,
          selling_price: product.selling_price,
          sale_unit: product.sale_unit,
          kind: product.kind,
          inventory_item_id: product.inventory_item ?? '',
          branch_ids: product.branch_ids,
          is_active: product.is_active,
        }
      : emptyProduct,
  )
  const save = useMutation({
    mutationFn: () => {
      const input = {
        ...form,
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

  if (product && !editing) {
    return (
      <Modal open wide title={product.name} onClose={onClose}>
        <dl className="grid gap-3 sm:grid-cols-2">
          <Fact label="Product code" value={product.sku} />
          <Fact label="Category" value={product.category || '—'} />
          <Fact label="Selling price" value={product.selling_price} />
          <Fact label="Unit" value={unitLabel(product.sale_unit)} />
          <Fact label="Type" value={kindLabel(product.kind)} />
          <Fact label="Stock item" value={product.inventory_item_name || 'Not linked'} />
          <Fact label="Branches" value={branchNames(product, branches)} />
          <Fact label="Status" value={product.is_active ? 'Active' : 'Inactive'} />
        </dl>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Close</Button>
          {canEdit ? <Button onClick={onEdit}>Edit</Button> : null}
        </div>
      </Modal>
    )
  }

  return (
    <Modal open wide title={product ? 'Edit product' : 'New product'} onClose={onClose}>
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault()
          save.mutate()
        }}
      >
        <TextField label="Product name" required value={form.name} onChange={(event) => set('name', event.target.value)} />
        <TextField
          label="Product code"
          value={product?.sku || 'Assigned when you save'}
          disabled
          hint="Created automatically, like PRD-0001. This cannot be changed."
        />
        <TextField label="Category" value={form.category} onChange={(event) => set('category', event.target.value)} />
        <TextField label="Selling price" required value={form.selling_price} onChange={(event) => set('selling_price', event.target.value)} />
        <SelectField label="Unit" value={form.sale_unit} onChange={(event) => set('sale_unit', event.target.value)}>
          {stockUnits.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </SelectField>
        <SelectField label="Product type" value={form.kind} onChange={(event) => set('kind', event.target.value)}>
          {itemKinds.filter(([value]) => value !== 'PACKAGING').map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </SelectField>
        <div className="sm:col-span-2">
          <SelectField
            label="Inventory item"
            hint="The stock item this product is made from. Create it under Inventory first."
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
          <input type="checkbox" checked={form.is_active} onChange={(event) => set('is_active', event.target.checked)} />
          Active
        </label>
        {save.isError ? <p className="text-sm text-danger sm:col-span-2">{errorMessage(save.error)}</p> : null}
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button variant="secondary" onClick={product ? onBack : onClose}>Cancel</Button>
          <Button type="submit" disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Save product'}</Button>
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
