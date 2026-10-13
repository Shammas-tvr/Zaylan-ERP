import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createRecipe, listItems, listProducts, listRecipes, type ProductMaster } from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { SelectField, TextField } from '../../shared/ui/Field.tsx'
import { ErrorState } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { Panel } from '../../shared/ui/PageHeader.tsx'
import { useWorkspace } from '../workspace/queries.ts'
import { stockUnits, unitLabel } from './catalogLabels.ts'
import { Pager, usePagedRows } from './listTools.tsx'

export function RecipesPage() {
  const workspace = useWorkspace()
  const context = workspace.data
  const recipesOn = (context?.subscription.features ?? []).includes('recipes')
  const recipes = useQuery({ queryKey: ['recipes'], queryFn: listRecipes, enabled: Boolean(context && recipesOn) })
  const products = useQuery({ queryKey: ['products'], queryFn: listProducts, enabled: Boolean(context && recipesOn) })
  const items = useQuery({ queryKey: ['items'], queryFn: listItems, enabled: Boolean(context && recipesOn) })
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const filtered = (recipes.data ?? []).filter((recipe) => {
    const haystack = `${recipe.product_name || ''} ${recipe.output_name}`.toLowerCase()
    return haystack.includes(query.trim().toLowerCase())
  })
  const paged = usePagedRows(filtered, query)
  if (!context) return null
  const canManage = can(context.permissions, 'catalog.manage')

  return (
    <div className="grid gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Recipes & BOM</h2>
          <p className="text-sm text-ink-soft">Step 2: choose what you make and the ingredients it needs</p>
        </div>
        {canManage && recipesOn ? <Button onClick={() => setOpen(true)}>New recipe</Button> : null}
      </div>
      {recipesOn ? (
        <>
          <label className="grid max-w-sm gap-1.5 text-sm">
            <span className="font-medium">Search</span>
            <input
              className="h-11 rounded-xl border border-line bg-cream px-3"
              value={query}
              placeholder="Product or output item"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          {recipes.isError ? <ErrorState error={recipes.error} onRetry={() => void recipes.refetch()} /> : (
            <Panel>
              <DataTable
                caption="Recipes"
                rows={paged.rows}
                rowKey={(recipe) => recipe.id}
                empty={query ? 'No recipes match that search.' : 'No recipes yet. Link a product to an inventory item, or choose a semi-finished item as the output.'}
                columns={[
                  { header: 'Output', render: (recipe) => <span className="font-medium">{recipe.product_name || recipe.output_name}</span> },
                  { header: 'Version', render: (recipe) => `v${recipe.version}` },
                  { header: 'From', render: (recipe) => recipe.effective_from },
                  { header: 'Yield', render: (recipe) => recipe.yield_quantity },
                  { header: 'Wastage', render: (recipe) => `${recipe.expected_waste_percent}%` },
                  { header: 'Ingredient cost', render: (recipe) => recipe.ingredient_cost },
                  { header: 'Status', render: (recipe) => (recipe.is_active ? 'Active' : 'Inactive') },
                  {
                    header: 'Ingredients',
                    render: (recipe) =>
                      recipe.lines
                        .map((line) => {
                          const nested = line.nested_recipe ? ` (uses ${line.nested_recipe.output_name} v${line.nested_recipe.version})` : ''
                          const when = line.consume_at === 'SALE' ? 'at sale' : 'in production'
                          return `${line.quantity} ${unitLabel(line.unit)} ${line.ingredient_name} ${when}${nested}`
                        })
                        .join(', '),
                  },
                ]}
              />
              <Pager page={paged.page} pages={paged.pages} onPage={paged.setPage} />
            </Panel>
          )}
        </>
      ) : (
        <Panel>
          <p className="text-sm text-ink-soft">Recipes are not included in this plan.</p>
        </Panel>
      )}
      {open ? (
        <RecipeModal
          products={products.data ?? []}
          items={items.data ?? []}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </div>
  )
}

function RecipeModal({
  products,
  items,
  onClose,
}: {
  products: ProductMaster[]
  items: Array<{ id: string; name: string; sku: string; kind: string; stock_unit?: string; base_unit?: string }>
  onClose: () => void
}) {
  const queryClient = useQueryClient()
  const linked = products.filter((product) => product.inventory_item)
  const outputs = items.filter((item) => item.kind === 'SEMI' || item.kind === 'FINISHED')
  const [target, setTarget] = useState(linked[0] ? `product:${linked[0].id}` : outputs[0] ? `item:${outputs[0].id}` : '')
  const [yieldQty, setYieldQty] = useState('1')
  const [waste, setWaste] = useState('0')
  const [effectiveFrom, setEffectiveFrom] = useState(() => new Date().toISOString().slice(0, 10))
  const [lines, setLines] = useState([
    { ingredient_id: items[0]?.id ?? '', quantity: '1', unit: items[0]?.stock_unit || 'G', consume_at: 'PRODUCTION' },
  ])
  const create = useMutation({
    mutationFn: createRecipe,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['recipes'] })
      onClose()
    },
  })
  const outputItemId = target.startsWith('item:') ? target.slice(5) : ''
  const productId = target.startsWith('product:') ? target.slice(8) : ''
  const blockedIngredient = productId
    ? linked.find((product) => product.id === productId)?.inventory_item
    : outputItemId
  return (
    <Modal open wide title="New recipe" onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate({
            product_id: productId || undefined,
            output_item_id: outputItemId || undefined,
            effective_from: effectiveFrom,
            yield_quantity: yieldQty,
            expected_waste_percent: waste,
            lines,
          })
        }}
      >
        {linked.length === 0 && outputs.length === 0 ? (
          <p className="text-sm text-ink-soft">Create a semi-finished or finished inventory item first. Sellable products need that item linked before they can have a recipe.</p>
        ) : (
          <>
            <SelectField label="What this recipe makes" value={target} onChange={(event) => setTarget(event.target.value)}>
              {linked.length ? <optgroup label="Products">
                {linked.map((product) => (
                  <option key={product.id} value={`product:${product.id}`}>{product.name}</option>
                ))}
              </optgroup> : null}
              {outputs.length ? <optgroup label="Inventory items">
                {outputs.map((item) => (
                  <option key={item.id} value={`item:${item.id}`}>{item.name} ({item.sku})</option>
                ))}
              </optgroup> : null}
            </SelectField>
            <div className="grid gap-4 sm:grid-cols-3">
              <TextField label="Expected yield" required value={yieldQty} onChange={(event) => setYieldQty(event.target.value)} hint="How many this batch makes." />
              <TextField label="Expected wastage %" required value={waste} onChange={(event) => setWaste(event.target.value)} />
              <TextField label="Effective from" required type="date" value={effectiveFrom} onChange={(event) => setEffectiveFrom(event.target.value)} />
            </div>
            {lines.map((line, index) => {
              const ingredient = items.find((item) => item.id === line.ingredient_id)
              return (
                <div key={index} className="grid gap-3 rounded-2xl border border-line p-3 sm:grid-cols-2">
                  <SelectField
                    label="Ingredient"
                    value={line.ingredient_id}
                    onChange={(event) => {
                      const next = items.find((item) => item.id === event.target.value)
                      setLines((current) =>
                        current.map((row, rowIndex) =>
                          rowIndex === index
                            ? { ...row, ingredient_id: event.target.value, unit: next?.stock_unit || next?.base_unit || row.unit }
                            : row,
                        ),
                      )
                    }}
                  >
                    {items
                      .filter((item) => item.id !== blockedIngredient)
                      .map((item) => (
                        <option key={item.id} value={item.id}>{item.name}</option>
                      ))}
                  </SelectField>
                  <TextField
                    label="Quantity"
                    required
                    value={line.quantity}
                    onChange={(event) =>
                      setLines((current) => current.map((row, rowIndex) => (rowIndex === index ? { ...row, quantity: event.target.value } : row)))
                    }
                  />
                  <SelectField
                    label="Unit"
                    value={line.unit}
                    onChange={(event) =>
                      setLines((current) => current.map((row, rowIndex) => (rowIndex === index ? { ...row, unit: event.target.value } : row)))
                    }
                  >
                    {stockUnits.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </SelectField>
                  <SelectField
                    label="Consumed"
                    value={line.consume_at}
                    hint={ingredient?.kind === 'SEMI' ? 'Produce this semi-finished item first. The recipe does not explode it again.' : undefined}
                    onChange={(event) =>
                      setLines((current) => current.map((row, rowIndex) => (rowIndex === index ? { ...row, consume_at: event.target.value } : row)))
                    }
                  >
                    <option value="PRODUCTION">In the kitchen</option>
                    <option value="SALE">When the branch sells</option>
                  </SelectField>
                </div>
              )
            })}
            <Button
              type="button"
              variant="secondary"
              onClick={() =>
                setLines((current) => [
                  ...current,
                  { ingredient_id: items.find((item) => item.id !== blockedIngredient)?.id ?? '', quantity: '1', unit: 'G', consume_at: 'PRODUCTION' },
                ])
              }
            >
              Add ingredient
            </Button>
            <p className="text-sm text-ink-soft">Each ingredient is used either in the kitchen or at sale, never both. Ingredient cost uses the cost stored on the inventory item. A new save creates the next version.</p>
          </>
        )}
        {create.isError ? <p className="text-sm text-danger">{errorMessage(create.error)}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={create.isPending || !target}>Save recipe</Button>
        </div>
      </form>
    </Modal>
  )
}
