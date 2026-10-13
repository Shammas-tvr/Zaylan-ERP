export const itemKinds = [
  ['RAW', 'Raw material'],
  ['PACKAGING', 'Packaging'],
  ['SEMI', 'Semi-finished'],
  ['FINISHED', 'Finished product'],
] as const

export const stockUnits = [
  ['G', 'Gram'],
  ['KG', 'Kilogram'],
  ['ML', 'Millilitre'],
  ['L', 'Litre'],
  ['EACH', 'Piece'],
  ['BOX', 'Box'],
] as const

export const unitShort: Record<string, string> = {
  G: 'g',
  KG: 'kg',
  ML: 'ml',
  L: 'L',
  EACH: 'piece',
  BOX: 'box',
}

export const costingMethods = [
  ['MOVING_AVERAGE', 'Moving weighted average'],
  ['FIFO', 'FIFO'],
] as const

export function kindLabel(kind: string) {
  return itemKinds.find(([value]) => value === kind)?.[1] ?? kind
}

export function unitLabel(unit: string) {
  return unitShort[unit] ?? unit
}

const baseFactor: Record<string, number> = { G: 1, KG: 1000, ML: 1, L: 1000, EACH: 1, BOX: 1 }

export function defaultPurchaseFactor(purchaseUnit: string, stockUnit: string) {
  if (purchaseUnit === 'KG' && stockUnit === 'G') return '1000'
  if (purchaseUnit === 'L' && stockUnit === 'ML') return '1000'
  if (purchaseUnit === stockUnit) return '1'
  return '1'
}

export function stockNumber(quantity: string, stockUnit: string) {
  const factor = baseFactor[stockUnit] ?? 1
  const value = Number(quantity) / factor
  return Number.isFinite(value) ? value : 0
}

export function expiryLabel(value: string | null | undefined) {
  if (!value) return '—'
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return value
  const date = new Date(year, month - 1, day)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const text = date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
  return date < today ? `${text} · expired` : text
}

export function stockFromBase(quantity: string, stockUnit: string) {
  const value = stockNumber(quantity, stockUnit)
  if (!Number.isFinite(Number(quantity))) return quantity
  return value.toLocaleString(undefined, { maximumFractionDigits: 3 })
}
