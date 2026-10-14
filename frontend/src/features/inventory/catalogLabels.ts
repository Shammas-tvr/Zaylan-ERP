export const itemKinds = [
  ['RAW', 'Ingredient'],
  ['PACKAGING', 'Packaging'],
  ['SEMI', 'Semi-finished product'],
  ['FINISHED', 'Finished product'],
  ['RESALE', 'Purchased resale item'],
] as const

export const stockUnits = [
  ['KG', 'Kilogram (kg)'],
  ['G', 'Gram (g)'],
  ['L', 'Litre (L)'],
  ['ML', 'Millilitre (ml)'],
  ['EACH', 'Piece'],
  ['BOX', 'Box'],
  ['PACKET', 'Packet'],
  ['BOTTLE', 'Bottle'],
  ['TRAY', 'Tray'],
] as const

export const unitShort: Record<string, string> = {
  G: 'g',
  KG: 'kg',
  ML: 'ml',
  L: 'L',
  EACH: 'piece',
  BOX: 'box',
  PACKET: 'packet',
  BOTTLE: 'bottle',
  TRAY: 'tray',
}

export const costingMethods = [
  ['FIFO', 'FIFO'],
  ['MOVING_AVERAGE', 'Weighted average'],
] as const

export const stockStatuses = [
  ['', 'All'],
  ['normal', 'Normal'],
  ['low', 'Low stock'],
  ['out', 'Out of stock'],
] as const

export function previewCode(name: string, existing: string[] = [], skip = '') {
  const letters = name.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 4)
  if (!letters) return ''
  const prefix = `${letters}-`
  let highest = 0
  for (const sku of existing) {
    const value = sku.toUpperCase()
    if (skip && value === skip.toUpperCase()) continue
    if (!value.startsWith(prefix)) continue
    const tail = value.slice(prefix.length)
    if (/^\d+$/.test(tail)) highest = Math.max(highest, Number(tail))
  }
  return `${prefix}${String(highest + 1).padStart(2, '0')}`
}

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
