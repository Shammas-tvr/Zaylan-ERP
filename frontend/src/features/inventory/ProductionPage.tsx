import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { completeProduction, createProduction, listProduction, listRecipes } from '../../shared/api/stock.ts'
import { errorMessage } from '../../shared/api/errors.ts'
import { usePageTitle } from '../../shared/hooks.ts'
import { can } from '../../shared/permissions.ts'
import { Button } from '../../shared/ui/Button.tsx'
import { DataTable } from '../../shared/ui/DataTable.tsx'
import { TextField } from '../../shared/ui/Field.tsx'
import { NoAccess } from '../../shared/ui/Feedback.tsx'
import { Modal } from '../../shared/ui/Modal.tsx'
import { PageHeader, Panel } from '../../shared/ui/PageHeader.tsx'
import { useWorkspace } from '../workspace/queries.ts'

export function ProductionPage() {
  usePageTitle('Production')
  const workspace = useWorkspace()
  const context = workspace.data
  const orders = useQuery({ queryKey: ['production'], queryFn: listProduction, enabled: Boolean(context) })
  const [open, setOpen] = useState(false)
  if (!context) return null
  if (!can(context.permissions, 'production.manage')) return <NoAccess />

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Production"
        description="Completing an order deducts kitchen ingredients and adds the output to the central kitchen."
        action={<Button onClick={() => setOpen(true)}>New production</Button>}
      />
      <Panel>
        <DataTable
          caption="Production orders"
          rows={orders.data ?? []}
          rowKey={(order) => order.id}
          empty="No production yet."
          columns={[
            { header: 'Recipe', render: (order) => <span className="font-medium">{order.recipe_name}</span> },
            { header: 'Planned', render: (order) => order.planned_quantity },
            { header: 'Actual', render: (order) => order.actual_quantity ?? '—' },
            { header: 'Waste', render: (order) => order.waste_quantity },
            { header: 'Status', render: (order) => order.status },
            {
              header: '',
              render: (order) =>
                order.status === 'DRAFT' ? <CompleteButton id={order.id} /> : null,
            },
          ]}
        />
      </Panel>
      {open ? <CreateModal onClose={() => setOpen(false)} /> : null}
    </div>
  )
}

function CompleteButton({ id }: { id: string }) {
  const queryClient = useQueryClient()
  const [actual, setActual] = useState('')
  const [waste, setWaste] = useState('0')
  const complete = useMutation({
    mutationFn: () => completeProduction(id, { actual_quantity: actual, waste_quantity: waste || '0' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['production'] }),
  })
  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={(event) => {
        event.preventDefault()
        complete.mutate()
      }}
    >
      <TextField label="Actual" required value={actual} onChange={(event) => setActual(event.target.value)} />
      <TextField label="Waste" value={waste} onChange={(event) => setWaste(event.target.value)} />
      <Button type="submit" disabled={complete.isPending}>Complete</Button>
      {complete.isError ? <p className="text-sm text-danger">{errorMessage(complete.error)}</p> : null}
    </form>
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
  return (
    <Modal open title="New production" onClose={onClose}>
      <form
        className="grid gap-4"
        onSubmit={(event) => {
          event.preventDefault()
          create.mutate({ recipe_id: selected, planned_quantity: planned })
        }}
      >
        <label className="grid gap-1.5 text-sm">
          <span className="font-medium">Recipe</span>
          <select className="h-11 rounded-xl border border-line bg-cream px-3" value={selected} onChange={(event) => setRecipeId(event.target.value)}>
            {(recipes.data ?? []).map((recipe) => (
              <option key={recipe.id} value={recipe.id}>
                {recipe.output_name} v{recipe.version}
              </option>
            ))}
          </select>
        </label>
        <TextField label="Planned quantity" required value={planned} onChange={(event) => setPlanned(event.target.value)} />
        {create.isError ? <p className="text-sm text-danger">{errorMessage(create.error)}</p> : null}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={create.isPending || !selected}>Create</Button>
        </div>
      </form>
    </Modal>
  )
}
