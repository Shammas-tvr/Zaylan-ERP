import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createItem, createRecipe, listItems, listRecipes } from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { SelectField, TextField } from '../../shared/ui/Field.tsx'
import { NoAccess } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel } from '../../shared/ui/PageHeader.tsx'
import { useWorkspace } from '../workspace/queries.ts'

const kinds = [
  ['RAW', 'Raw material'],
  ['PACKAGING', 'Packaging'],
  ['SEMI', 'Semi-finished'],
  ['FINISHED', 'Finished product'],
] as const

export function ProductsPage() {
  usePageTitle('Products')
  const workspace = useWorkspace()
  const context = workspace.data
  const items = useQuery({ queryKey: ['items'], queryFn: listItems, enabled: Boolean(context) })
  const recipes = useQuery({ queryKey: ['recipes'], queryFn: listRecipes, enabled: Boolean(context) })
  const [itemOpen, setItemOpen] = useState(false)
  const [recipeOpen, setRecipeOpen] = useState(false)
  if (!context) return null
  if (!can(context.permissions, 'catalog.view')) return <NoAccess />
  const canManage = can(context.permissions, 'catalog.manage')

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Products"
        description="Items and the recipe that says what is used in the kitchen and what is used when a branch sells."
        action={
          canManage ? (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setRecipeOpen(true)}>
                New recipe
              </Button>
              <Button onClick={() => setItemOpen(true)}>New item</Button>
            </div>
          ) : null
        }
      />
      <Panel>
        <DataTable
          caption="Items"
          rows={items.data ?? []}
          rowKey={(item) => item.id}
          empty="No items yet."
          columns={[
            { header: 'Item', render: (item) => <span className="font-medium">{item.name}</span> },
            { header: 'SKU', render: (item) => item.sku },
            { header: 'Kind', render: (item) => item.kind },
            { header: 'Unit', render: (item) => item.base_unit },
          ]}
        />
      </Panel>
      <Panel>
        <DataTable
          caption="Recipes"
          rows={recipes.data ?? []}
          rowKey={(recipe) => recipe.id}
          empty="No recipes yet."
          columns={[
            { header: 'Product', render: (recipe) => <span className="font-medium">{recipe.output_name}</span> },
            { header: 'Version', render: (recipe) => String(recipe.version) },
            { header: 'From', render: (recipe) => recipe.effective_from },
            {
              header: 'Uses',
              render: (recipe) =>
                recipe.lines.map((line) => `${line.quantity} ${line.unit} ${line.ingredient_name} (${line.consume_at})`).join(', '),
            },
          ]}
        />
      </Panel>
      {itemOpen ? <ItemModal onClose={() => setItemOpen(false)} /> : null}
      {recipeOpen ? <RecipeModal items={items.data ?? []} onClose={() => setRecipeOpen(false)} /> : null}
    </div>
  )
}

function ItemModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const create = useMutation({
    mutationFn: createItem,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['items'] })
      onClose()
    },
  })
  const [sku, setSku] = useState('')
  const [name, setName] = useState('')
  const [kind, setKind] = useState('RAW')
  const [unit, setUnit] = useState('G')
  return (
    <Modal open title="New item" onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate({ sku, name, kind, base_unit: unit })
        }}
      >
        <TextField label="Name" required value={name} onChange={(event) => setName(event.target.value)} />
        <TextField label="SKU" required value={sku} onChange={(event) => setSku(event.target.value.toUpperCase())} />
        <SelectField label="Kind" value={kind} onChange={(event) => setKind(event.target.value)}>
          {kinds.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </SelectField>
        <SelectField label="Base unit" value={unit} onChange={(event) => setUnit(event.target.value)}>
          <option value="G">Grams</option>
          <option value="ML">Millilitres</option>
          <option value="EACH">Each</option>
        </SelectField>
        {create.isError ? <p className="text-sm text-danger">{errorMessage(create.error)}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={create.isPending}>Save item</Button>
        </div>
      </form>
    </Modal>
  )
}

function RecipeModal({ items, onClose }: { items: Array<{ id: string; name: string }>; onClose: () => void }) {
  const queryClient = useQueryClient()
  const create = useMutation({
    mutationFn: createRecipe,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['recipes'] })
      onClose()
    },
  })
  const [output, setOutput] = useState(items[0]?.id ?? '')
  const [yieldQty, setYieldQty] = useState('1')
  const [lines, setLines] = useState([
    { ingredient_id: items[0]?.id ?? '', quantity: '1', unit: 'G', consume_at: 'PRODUCTION' },
  ])
  return (
    <Modal open title="New recipe version" onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate({
            output_item_id: output,
            effective_from: new Date().toISOString().slice(0, 10),
            yield_quantity: yieldQty,
            lines,
          })
        }}
      >
        <SelectField label="Output item" value={output} onChange={(event) => setOutput(event.target.value)}>
          {items.map((item) => (
            <option key={item.id} value={item.id}>{item.name}</option>
          ))}
        </SelectField>
        <TextField label="Yield" required value={yieldQty} onChange={(event) => setYieldQty(event.target.value)} />
        {lines.map((line, index) => (
          <div key={index} className="grid gap-2 rounded-2xl border border-line p-3">
            <SelectField
              label="Ingredient"
              value={line.ingredient_id}
              onChange={(event) =>
                setLines((current) =>
                  current.map((row, rowIndex) =>
                    rowIndex === index ? { ...row, ingredient_id: event.target.value } : row,
                  ),
                )
              }
            >
              {items.map((item) => (
                <option key={item.id} value={item.id}>{item.name}</option>
              ))}
            </SelectField>
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
            <SelectField
              label="Unit"
              value={line.unit}
              onChange={(event) =>
                setLines((current) =>
                  current.map((row, rowIndex) =>
                    rowIndex === index ? { ...row, unit: event.target.value } : row,
                  ),
                )
              }
            >
              <option value="G">g</option>
              <option value="KG">kg</option>
              <option value="ML">ml</option>
              <option value="L">L</option>
              <option value="EACH">each</option>
            </SelectField>
            <SelectField
              label="Consumed"
              value={line.consume_at}
              onChange={(event) =>
                setLines((current) =>
                  current.map((row, rowIndex) =>
                    rowIndex === index ? { ...row, consume_at: event.target.value } : row,
                  ),
                )
              }
            >
              <option value="PRODUCTION">During production</option>
              <option value="SALE">When sold</option>
            </SelectField>
          </div>
        ))}
        <Button
          type="button"
          variant="secondary"
          onClick={() =>
            setLines((current) => [
              ...current,
              { ingredient_id: items[0]?.id ?? '', quantity: '1', unit: 'G', consume_at: 'SALE' },
            ])
          }
        >
          Add ingredient
        </Button>
        <p className="text-sm text-ink-soft">A line is deducted only at production or at sale, never both.</p>
        {create.isError ? <p className="text-sm text-danger">{errorMessage(create.error)}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={create.isPending || !output}>Save recipe</Button>
        </div>
      </form>
    </Modal>
  )
}
