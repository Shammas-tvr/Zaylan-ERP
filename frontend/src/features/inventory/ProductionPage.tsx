import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  completeProduction,
  createProduction,
  listBalances,
  listProduction,
  listRecipes,
  type ProductionOrder,
  type Recipe,
} from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { TextField } from '../../shared/ui/Field.tsx'
import { NoAccess } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { Panel } from '../../shared/ui/PageHeader.tsx'
import { useWorkspace } from '../workspace/queries.ts'
import { stockFromBase, unitLabel } from './catalogLabels.ts'

export function ProductionPage() {
  const workspace = useWorkspace()
  const context = workspace.data
  const orders = useQuery({ queryKey: ['production'], queryFn: listProduction, enabled: Boolean(context) })
  const [open, setOpen] = useState(false)
  const [completing, setCompleting] = useState<ProductionOrder | null>(null)
  if (!context) return null
  if (!can(context.permissions, 'production.manage')) return <NoAccess />

  return (
    <div className="grid gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Production</h2>
          <p className="text-sm text-ink-soft">Step 3: make a batch. Ingredients are used up and the finished stock is added</p>
        </div>
        <Button onClick={() => setOpen(true)}>New production</Button>
      </div>
      <Panel>
        <DataTable
          caption="Production orders"
          rows={orders.data ?? []}
          rowKey={(order) => order.id}
          empty="No production yet. Choose a recipe and the quantity you plan to make."
          columns={[
            { header: 'Recipe', render: (order) => <span className="font-medium">{order.recipe_name}</span> },
            { header: 'Planned', render: (order) => order.planned_quantity },
            { header: 'Actual', render: (order) => order.actual_quantity ?? '—' },
            { header: 'Waste', render: (order) => order.waste_quantity },
            { header: 'Status', render: (order) => (order.status === 'DRAFT' ? 'Draft' : order.status === 'COMPLETED' ? 'Completed' : order.status) },
            {
              header: '',
              render: (order) =>
                order.status === 'DRAFT' ? (
                  <Button size="sm" onClick={() => setCompleting(order)}>Record output</Button>
                ) : null,
            },
          ]}
        />
      </Panel>
      {open ? <CreateModal onClose={() => setOpen(false)} /> : null}
      {completing ? <CompleteModal order={completing} onClose={() => setCompleting(null)} /> : null}
    </div>
  )
}

function needs(recipe: Recipe, quantity: string) {
  const planned = Number(quantity)
  const yieldQty = Number(recipe.yield_quantity) || 1
  if (!Number.isFinite(planned) || planned <= 0) return []
  const scale = planned / yieldQty
  return recipe.lines
    .filter((line) => line.consume_at === 'PRODUCTION')
    .map((line) => ({
      id: line.id,
      name: line.ingredient_name,
      sku: line.ingredient_sku || '',
      unit: line.unit,
      required: Number(line.quantity) * scale,
    }))
}

function IngredientPreview({ recipe, quantity }: { recipe: Recipe | undefined; quantity: string }) {
  const balances = useQuery({ queryKey: ['balances'], queryFn: listBalances })
  if (!recipe) return null
  const rows = needs(recipe, quantity)
  const saleLines = recipe.lines.filter((line) => line.consume_at === 'SALE')
  if (!quantity) return <p className="text-sm text-ink-soft">Enter a quantity to see the ingredients this batch needs.</p>
  return (
    <div className="grid gap-2 rounded-2xl border border-line p-3 text-sm">
      <p className="font-medium">Ingredients for this quantity</p>
      {rows.length === 0 ? <p className="text-ink-soft">This recipe has no kitchen ingredients. Sale ingredients are deducted when the branch sells.</p> : null}
      {rows.map((row) => {
        const onHand = (balances.data ?? [])
          .filter((balance) => balance.location_kind === 'CENTRAL_KITCHEN' && balance.item_sku === row.sku)
          .reduce((total, balance) => total + Number(balance.quantity), 0)
        return (
          <p key={row.id}>
            {row.required.toLocaleString(undefined, { maximumFractionDigits: 3 })} {unitLabel(row.unit)} {row.name}
            {row.sku ? ` · kitchen on hand ${stockFromBase(String(onHand), row.unit)} ${unitLabel(row.unit)}` : ''}
          </p>
        )
      })}
      {saleLines.length ? (
        <p className="text-ink-soft">
          Not deducted here: {saleLines.map((line) => line.ingredient_name).join(', ')}. Those are taken from the branch when the product is sold.
        </p>
      ) : null}
    </div>
  )
}

function CreateModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const recipes = useQuery({ queryKey: ['recipes'], queryFn: listRecipes })
  const create = useMutation({
    mutationFn: createProduction,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['production'] })
      onClose()
    },
  })
  const [recipeId, setRecipeId] = useState('')
  const [planned, setPlanned] = useState('')
  const selected = recipeId || recipes.data?.[0]?.id || ''
  const recipe = (recipes.data ?? []).find((row) => row.id === selected)
  return (
    <Modal open title="New production" onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate({ recipe_id: selected, planned_quantity: planned })
        }}
      >
        {(recipes.data ?? []).length === 0 ? (
          <p className="text-sm text-ink-soft">Add a recipe before you plan production.</p>
        ) : (
          <>
            <label className="grid gap-1.5 text-sm">
              <span className="font-medium">Recipe</span>
              <select className="h-11 rounded-xl border border-line bg-cream px-3" value={selected} onChange={(event) => setRecipeId(event.target.value)}>
                {(recipes.data ?? []).map((row) => (
                  <option key={row.id} value={row.id}>
                    {(row.product_name || row.output_name)} v{row.version}
                  </option>
                ))}
              </select>
            </label>
            <TextField label="Planned quantity" required value={planned} onChange={(event) => setPlanned(event.target.value)} hint="Saving a draft does not move stock." />
            <IngredientPreview recipe={recipe} quantity={planned} />
          </>
        )}
        {create.isError ? <p className="text-sm text-danger">{errorMessage(create.error)}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={create.isPending || !selected || !planned}>Save draft</Button>
        </div>
      </form>
    </Modal>
  )
}

function CompleteModal({ order, onClose }: { order: ProductionOrder; onClose: () => void }) {
  const queryClient = useQueryClient()
  const recipes = useQuery({ queryKey: ['recipes'], queryFn: listRecipes })
  const recipe = (recipes.data ?? []).find((row) => row.id === order.recipe)
  const [actual, setActual] = useState(order.planned_quantity)
  const [waste, setWaste] = useState('0')
  const [confirming, setConfirming] = useState(false)
  const complete = useMutation({
    mutationFn: () => completeProduction(order.id, { actual_quantity: actual, waste_quantity: waste || '0' }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['production'] })
      await queryClient.invalidateQueries({ queryKey: ['balances'] })
      await queryClient.invalidateQueries({ queryKey: ['movements'] })
      onClose()
    },
  })
  return (
    <Modal open title={`Record ${order.recipe_name}`} onClose={onClose}>
      {confirming ? (
        <div className="grid gap-4">
          <p className="text-sm text-ink-soft">
            Completing this order deducts the kitchen ingredients, adds {actual} to stock, and records {waste || '0'} as waste. It cannot be edited afterwards. If the kitchen is short of an ingredient, nothing is posted.
          </p>
          <IngredientPreview recipe={recipe} quantity={actual} />
          {complete.isError ? <p className="text-sm text-danger">{errorMessage(complete.error)}</p> : null}
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirming(false)}>Back</Button>
            <Button disabled={complete.isPending} onClick={() => complete.mutate()}>
              {complete.isPending ? 'Completing…' : 'Complete production'}
            </Button>
          </div>
        </div>
      ) : (
        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            setConfirming(true)
          }}
        >
          <TextField label="Actual output" required value={actual} onChange={(event) => setActual(event.target.value)} />
          <TextField label="Waste" value={waste} onChange={(event) => setWaste(event.target.value)} hint="Waste cannot be more than the amount produced." />
          <IngredientPreview recipe={recipe} quantity={actual} />
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={onClose}>Cancel</Button>
            <Button type="submit">Review</Button>
          </div>
        </form>
      )}
    </Modal>
  )
}
