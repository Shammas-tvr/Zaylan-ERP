import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createRecipe, listItems, listRecipes, type ProductMaster } from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { SelectField, TextField } from '../../shared/ui/Field.tsx'
import { Panel } from '../../shared/ui/PageHeader.tsx'
import { stockUnits, unitLabel } from './catalogLabels.ts'

export function ProductRecipe({ product, canEdit }: { product: ProductMaster; canEdit: boolean }) {
  const queryClient = useQueryClient()
  const recipes = useQuery({ queryKey: ['recipes'], queryFn: listRecipes })
  const items = useQuery({ queryKey: ['items'], queryFn: listItems })
  const mine = (recipes.data ?? [])
    .filter((recipe) => recipe.product === product.id)
    .sort((a, b) => b.version - a.version)
  const current = mine.find((recipe) => recipe.status !== 'DRAFT' && recipe.is_active) ?? mine[0]
  const [open, setOpen] = useState(false)

  return (
    <Panel>
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-2xl tracking-tight">Recipe</h2>
          <p className="mt-1 text-sm text-ink-soft">
            {current
              ? `Version ${current.version} · ${current.status === 'DRAFT' ? 'Draft' : 'Confirmed'} · ingredient cost ${current.ingredient_cost_per_unit ?? current.ingredient_cost} per unit. Editing a recipe does not change stock.`
              : 'No recipe yet. Add ingredients from inventory. This does not change stock.'}
          </p>
        </div>
        {canEdit ? <Button variant="secondary" onClick={() => setOpen((value) => !value)}>{open ? 'Close' : current ? 'New version' : 'Add recipe'}</Button> : null}
      </div>
      {current ? (
        <ul className="mt-4 grid gap-2 text-sm">
          {current.lines.map((line) => (
            <li key={line.id} className="flex justify-between gap-3 border-b border-line/70 py-2">
              <span>{line.ingredient_name}</span>
              <span className="text-ink-soft">{line.quantity} {unitLabel(line.unit)} · {line.line_cost ?? '—'}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {open ? (
        <RecipeForm
          product={product}
          items={(items.data ?? []).filter((item) => item.id !== product.inventory_item)}
          onSaved={async () => {
            setOpen(false)
            await queryClient.invalidateQueries({ queryKey: ['recipes'] })
            await queryClient.invalidateQueries({ queryKey: ['products'] })
          }}
        />
      ) : null}
    </Panel>
  )
}

function RecipeForm({
  product,
  items,
  onSaved,
}: {
  product: ProductMaster
  items: Array<{ id: string; name: string; sku: string; stock_unit?: string; base_unit?: string }>
  onSaved: () => Promise<void>
}) {
  const [yieldQty, setYieldQty] = useState('1')
  const [waste, setWaste] = useState('0')
  const [status, setStatus] = useState<'DRAFT' | 'CONFIRMED'>('CONFIRMED')
  const [lines, setLines] = useState([{ ingredient_id: items[0]?.id ?? '', quantity: '1', unit: items[0]?.stock_unit || 'G' }])
  const save = useMutation({
    mutationFn: () => createRecipe({
      product_id: product.id,
      effective_from: new Date().toISOString().slice(0, 10),
      yield_quantity: yieldQty,
      expected_waste_percent: waste,
      status,
      lines: lines.map((line) => ({ ...line, consume_at: 'PRODUCTION' })),
    }),
    onSuccess: () => onSaved(),
  })
  return (
    <form className="mt-5 grid gap-3" onSubmit={(event) => { event.preventDefault(); save.mutate() }}>
      <div className="grid gap-3 sm:grid-cols-3">
        <TextField label="Yield" required value={yieldQty} onChange={(event) => setYieldQty(event.target.value)} hint="Finished units this recipe makes." />
        <TextField label="Expected wastage %" value={waste} onChange={(event) => setWaste(event.target.value)} />
        <SelectField label="Status" value={status} onChange={(event) => setStatus(event.target.value as 'DRAFT' | 'CONFIRMED')}>
          <option value="CONFIRMED">Confirmed</option>
          <option value="DRAFT">Draft</option>
        </SelectField>
      </div>
      {lines.map((line, index) => (
        <div key={index} className="grid gap-3 sm:grid-cols-[1.4fr_0.6fr_0.6fr_auto]">
          <SelectField
            label="Ingredient"
            value={line.ingredient_id}
            onChange={(event) => {
              const next = items.find((item) => item.id === event.target.value)
              setLines((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, ingredient_id: event.target.value, unit: next?.stock_unit || row.unit } : row))
            }}
          >
            {items.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.sku})</option>)}
          </SelectField>
          <TextField label="Quantity" required value={line.quantity} onChange={(event) => setLines((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, quantity: event.target.value } : row))} />
          <SelectField label="Unit" value={line.unit} onChange={(event) => setLines((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, unit: event.target.value } : row))}>
            {stockUnits.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </SelectField>
          <Button type="button" variant="secondary" className="self-end" onClick={() => setLines((current) => current.filter((_, rowIndex) => rowIndex !== index))}>Remove</Button>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="secondary" onClick={() => setLines((current) => [...current, { ingredient_id: items[0]?.id ?? '', quantity: '1', unit: 'G' }])}>Add ingredient</Button>
        <Button type="submit" disabled={save.isPending || lines.length === 0}>{save.isPending ? 'Saving…' : 'Save recipe'}</Button>
      </div>
      {save.isError ? <p className="text-sm text-danger">{errorMessage(save.error)}</p> : null}
    </form>
  )
}
