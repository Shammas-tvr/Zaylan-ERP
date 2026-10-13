import { client } from './client.ts'

export type StockItem = {
  id: string
  sku: string
  name: string
  kind: string
  base_unit: string
  is_active: boolean
}

export type RecipeLine = {
  id: string
  ingredient: string
  ingredient_name: string
  quantity: string
  unit: string
  consume_at: string
}

export type Recipe = {
  id: string
  output_item: string
  output_name: string
  version: number
  effective_from: string
  yield_quantity: string
  lines: RecipeLine[]
}

export type Balance = {
  id: string
  location: string
  location_name: string
  location_kind: string
  item_name: string
  item_sku: string
  base_unit: string
  quantity: string
}

export type ProductionOrder = {
  id: string
  recipe: string
  recipe_name: string
  planned_quantity: string
  actual_quantity: string | null
  waste_quantity: string
  status: string
}

export type TransferLine = {
  id: string
  item: string
  item_name: string
  unit: string
  requested_quantity: string
  dispatched_quantity: string
  received_quantity: string | null
  discrepancy_note: string
}

export type Transfer = {
  id: string
  number: string
  status: string
  destination_name: string
  branch_id: string | null
  lines: TransferLine[]
}

export type SaleRow = {
  id: string
  branch: string
  branch_name: string
  status: string
  lines: Array<{ id: string; item_name: string; quantity: string }>
}

async function getList<T>(url: string) {
  const { data } = await client.get<T[] | { results: T[] }>(url)
  return Array.isArray(data) ? data : data.results
}

export const listItems = () => getList<StockItem>('/catalog/items/')
export const listRecipes = () => getList<Recipe>('/catalog/recipes/')
export const listBalances = () => getList<Balance>('/inventory/balances')
export const listProduction = () => getList<ProductionOrder>('/inventory/production/')
export const listTransfers = () => getList<Transfer>('/inventory/transfers/')
export const listSales = () => getList<SaleRow>('/sales/')

export async function createItem(input: { sku: string; name: string; kind: string; base_unit: string }) {
  const { data } = await client.post<StockItem>('/catalog/items/', input)
  return data
}

export async function createRecipe(input: {
  output_item_id: string
  effective_from: string
  yield_quantity: string
  lines: Array<{ ingredient_id: string; quantity: string; unit: string; consume_at: string }>
}) {
  const { data } = await client.post<Recipe>('/catalog/recipes/', input)
  return data
}

export async function createProduction(input: { recipe_id: string; planned_quantity: string }) {
  const { data } = await client.post<ProductionOrder>('/inventory/production/', input)
  return data
}

export async function completeProduction(id: string, input: { actual_quantity: string; waste_quantity: string }) {
  const { data } = await client.post<ProductionOrder>(`/inventory/production/${id}/complete/`, input)
  return data
}

export async function createTransfer(input: {
  branch_id: string
  lines: Array<{ item_id: string; quantity: string; unit: string }>
}) {
  const { data } = await client.post<Transfer>('/inventory/transfers/', input)
  return data
}

export async function approveTransfer(id: string) {
  const { data } = await client.post<Transfer>(`/inventory/transfers/${id}/approve/`)
  return data
}

export async function dispatchTransfer(id: string) {
  const { data } = await client.post<Transfer>(`/inventory/transfers/${id}/dispatch/`)
  return data
}

export async function receiveTransfer(
  id: string,
  lines: Array<{ line_id: string; received_quantity: string; note: string }>,
) {
  const { data } = await client.post<Transfer>(`/inventory/transfers/${id}/receive/`, { lines })
  return data
}

export async function recordSale(input: {
  branch_id: string
  idempotency_key: string
  lines: Array<{ item_id: string; quantity: string }>
}) {
  const { data } = await client.post<SaleRow>('/sales/', input)
  return data
}

export async function refundSale(id: string) {
  const { data } = await client.post<SaleRow>(`/sales/${id}/refund/`)
  return data
}
