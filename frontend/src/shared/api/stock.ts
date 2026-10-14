import { client } from './client.ts'

export type StockItem = {
  id: string
  sku: string
  name: string
  kind: string
  category: string
  base_unit: string
  stock_unit: string
  purchase_unit: string
  purchase_factor: string
  supplier_name: string
  default_supplier: string | null
  default_supplier_name: string | null
  supplier_ids: string[]
  stock_policies: Array<{ location: string; location_name: string; minimum_quantity: string }>
  costing_method: string
  standard_cost: string
  minimum_stock: string
  storage_location: string | null
  storage_location_name: string | null
  branch_quantity: string | null
  branch_minimum: string | null
  stock_status: 'normal' | 'low' | 'out' | 'unstocked' | null
  tracks_batch: boolean
  tracks_expiry: boolean
  expiry_date: string | null
  tracks_stock: boolean
  image_key: string
  image_url: string | null
  is_active: boolean
}

export type ProductCosting = {
  recipe_id: string | null
  recipe_status: string
  recipe_version: number | null
  ingredient_cost: string
  labour_cost: string
  overhead_cost: string
  estimated_cost: string
  gross_profit: string | null
  gross_margin: string | null
}

export type ProductMaster = {
  id: string
  sku: string
  name: string
  category: string
  description: string
  image_key: string
  image_url: string | null
  selling_price: string
  labour_cost: string
  overhead_cost: string
  sale_unit: string
  kind: string
  inventory_item: string | null
  inventory_item_name: string | null
  branch_ids: string[]
  is_active: boolean
  costing: ProductCosting
}

export type ItemInput = {
  sku?: string
  name: string
  kind: string
  category?: string
  stock_unit: string
  purchase_unit?: string
  purchase_factor?: string
  supplier_name?: string
  default_supplier_id?: string | null
  supplier_ids?: string[]
  stock_policies?: Array<{ location_id: string; minimum_quantity: string }>
  costing_method: string
  standard_cost: string
  minimum_stock?: string
  storage_location_id?: string | null
  tracks_batch?: boolean
  tracks_expiry?: boolean
  expiry_date?: string | null
  tracks_stock?: boolean
  image_key?: string
  is_active?: boolean
}

export type RecipeLine = {
  id: string
  ingredient: string
  ingredient_name: string
  quantity: string
  unit: string
  consume_at: string
  line_cost?: string
  ingredient_sku?: string
  nested_recipe?: { id: string; version: number; output_name: string } | null
}

export type Recipe = {
  id: string
  output_item: string
  output_name: string
  product_name?: string | null
  version: number
  effective_from: string
  yield_quantity: string
  expected_waste_percent: string
  product: string | null
  ingredient_cost: string
  ingredient_cost_per_unit?: string
  status?: string
  is_active: boolean
  lines: RecipeLine[]
}

export type Balance = {
  id: string
  location: string
  location_name: string
  location_kind: string
  item_name: string
  item_sku: string
  item_kind: string
  category: string
  base_unit: string
  stock_unit: string
  minimum_stock: string
  expiry_date: string | null
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
  source_name: string
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

export function listItemsAt(location: string) {
  return getList<StockItem>(`/catalog/items/?location=${encodeURIComponent(location)}`)
}

export type Supplier = { id: string; name: string; is_active: boolean }

export const listSuppliers = () => getList<Supplier>('/catalog/suppliers/')

export async function requestImageUpload(input: { purpose: 'product' | 'item'; content_type: string; filename: string }) {
  const { data } = await client.post<{ object_key: string; upload_url: string; headers: Record<string, string>; max_bytes: number }>(
    '/catalog/images/',
    input,
  )
  return data
}

export async function uploadCatalogImage(file: File, purpose: 'product' | 'item') {
  const ticket = await requestImageUpload({ purpose, content_type: file.type, filename: file.name })
  if (file.size > ticket.max_bytes) {
    throw new Error('That image is too large.')
  }
  const response = await fetch(ticket.upload_url, { method: 'PUT', body: file, headers: ticket.headers })
  if (!response.ok) throw new Error('The image could not be uploaded.')
  return ticket.object_key
}

export async function createSupplier(name: string) {
  const { data } = await client.post<Supplier>('/catalog/suppliers/', { name })
  return data
}
export const listProducts = () => getList<ProductMaster>('/catalog/products/')
export const listRecipes = () => getList<Recipe>('/catalog/recipes/')
export type StockLocation = {
  id: string
  kind: string
  name: string
  branch: string | null
}

export const listBalances = () => getList<Balance>('/inventory/balances')
export const listLocations = () => getList<StockLocation>('/inventory/locations')

export type StockMovementRow = {
  id: string
  created_at: string
  item_name: string
  item_sku: string
  location_name: string
  quantity: string
  base_unit: string
  stock_unit: string
  reason: string
  note: string
}

export function listMovements(params: {
  location?: string
  reason?: string
  kind?: string
  category?: string
  from?: string
  to?: string
}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value)
  }
  const suffix = query.toString() ? `?${query}` : ''
  return getList<StockMovementRow>(`/inventory/movements${suffix}`)
}

export async function adjustStock(input: {
  location_id: string
  item_id: string
  quantity: string
  unit: string
  direction: 'in' | 'out'
  reason: 'WASTAGE' | 'EXPIRY' | 'ADJUSTMENT'
  note: string
}) {
  const { data } = await client.post('/inventory/adjustments', input)
  return data
}

export async function addStock(input: {
  location_id: string
  item_id: string
  quantity: string
  unit: string
  note?: string
}) {
  const { data } = await client.post('/inventory/adjustments', {
    ...input,
    direction: 'in',
    reason: 'ADJUSTMENT',
    note: input.note ?? 'Opening stock',
  })
  return data
}
export const listProduction = () => getList<ProductionOrder>('/inventory/production/')
export const listTransfers = () => getList<Transfer>('/inventory/transfers/')
export const listSales = () => getList<SaleRow>('/sales/')

export async function createItem(input: ItemInput) {
  const { data } = await client.post<StockItem>('/catalog/items/', input)
  return data
}

export async function updateItem(id: string, input: Partial<ItemInput>) {
  const { data } = await client.patch<StockItem>(`/catalog/items/${id}/`, input)
  return data
}

export type ProductInput = {
  sku?: string
  name: string
  category?: string
  description?: string
  image_key?: string
  selling_price: string
  labour_cost?: string
  overhead_cost?: string
  sale_unit: string
  kind: string
  inventory_item_id?: string | null
  branch_ids: string[]
  is_active: boolean
}

export async function createProduct(input: ProductInput) {
  const { data } = await client.post<ProductMaster>('/catalog/products/', input)
  return data
}

export async function updateProduct(id: string, input: Partial<ProductInput>) {
  const { data } = await client.patch<ProductMaster>(`/catalog/products/${id}/`, input)
  return data
}

export async function createRecipe(input: {
  output_item_id?: string
  product_id?: string
  effective_from: string
  yield_quantity: string
  expected_waste_percent?: string
  status?: 'DRAFT' | 'CONFIRMED'
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
  source_location_id?: string
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

export async function closeTransfer(id: string) {
  const { data } = await client.post<Transfer>(`/inventory/transfers/${id}/close/`)
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
