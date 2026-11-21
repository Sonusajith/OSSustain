export function asRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

export function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

export function asNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

export function asString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined
}

export function formatCount(value: unknown): string {
  const number = asNumber(value)
  return number === undefined ? '—' : new Intl.NumberFormat().format(number)
}

export function formatDecimal(value: unknown, digits = 3): string {
  const number = asNumber(value)
  return number === undefined ? '—' : number.toFixed(digits)
}

export function formatRate(value: unknown): string {
  const number = asNumber(value)
  return number === undefined ? '—' : `${(number * 100).toFixed(1)}%`
}

export function humanize(value: unknown): string {
  return typeof value === 'string'
    ? value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
    : '—'
}

export function nestedRecord(value: unknown, ...keys: string[]): Record<string, unknown> {
  return keys.reduce<Record<string, unknown>>((current, key) => asRecord(current[key]), asRecord(value))
}

export function formatInterval(value: unknown, low: unknown, high: unknown): string {
  const estimate = formatDecimal(value)
  if (estimate === '—') return estimate
  const lower = formatDecimal(low)
  const upper = formatDecimal(high)
  return lower === '—' || upper === '—' ? estimate : `${estimate} [${lower}, ${upper}]`
}
