/** Local JSON/CSV export + restore for trip history (iOS eviction resilience). */

import type { TripStub } from '../types'

export const EXPORT_FORMAT = 'accordos-trips'
export const EXPORT_VERSION = 1

export interface TripExportDocument {
  format: typeof EXPORT_FORMAT
  version: number
  exported_at: string
  trips: TripStub[]
  note?: string
}

const CSV_FIELDS = [
  'id',
  'state',
  'status',
  'start',
  'end',
  'distance_mi',
  'duration_s',
  'duration_min',
  'avg_speed_mph',
  'max_speed_mph',
  'idle_time_s',
  'fuel_used_pct',
  'fuel_estimate_status',
  'efficiency_score',
  'efficiency_status',
  'incomplete',
  'simulated',
  'revision',
  'title',
  'note',
] as const

function cell(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'boolean') return value ? '1' : '0'
  const s = String(value)
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

export function buildExportDocument(trips: TripStub[]): TripExportDocument {
  return {
    format: EXPORT_FORMAT,
    version: EXPORT_VERSION,
    exported_at: new Date().toISOString(),
    trips: trips.map((t) => ({ ...t })),
    note: 'Local AccordOS trip replica — restore after iOS storage eviction',
  }
}

export function exportTripsJson(trips: TripStub[]): string {
  return `${JSON.stringify(buildExportDocument(trips), null, 2)}\n`
}

export function parseTripsJson(raw: string): TripStub[] {
  const parsed = JSON.parse(raw) as TripExportDocument | TripStub[]
  if (Array.isArray(parsed)) {
    return parsed.filter((t) => t && typeof t.id === 'string')
  }
  if (
    parsed &&
    typeof parsed === 'object' &&
    parsed.format === EXPORT_FORMAT &&
    Array.isArray(parsed.trips)
  ) {
    return parsed.trips.filter((t) => t && typeof t.id === 'string')
  }
  throw new Error('Unrecognized trip export JSON')
}

export function exportTripsCsv(trips: TripStub[]): string {
  const header = CSV_FIELDS.join(',')
  const lines = trips.map((t) => {
    const row = t as unknown as Record<string, unknown>
    return CSV_FIELDS.map((f) => cell(row[f])).join(',')
  })
  return `${header}\n${lines.join('\n')}${lines.length ? '\n' : ''}`
}

function parseCsvLine(line: string): string[] {
  const out: string[] = []
  let cur = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]!
    if (inQuotes) {
      if (ch === '"' && line[i + 1] === '"') {
        cur += '"'
        i++
      } else if (ch === '"') {
        inQuotes = false
      } else {
        cur += ch
      }
    } else if (ch === '"') {
      inQuotes = true
    } else if (ch === ',') {
      out.push(cur)
      cur = ''
    } else {
      cur += ch
    }
  }
  out.push(cur)
  return out
}

export function parseTripsCsv(raw: string): TripStub[] {
  const lines = raw
    .split(/\r?\n/)
    .map((l) => l.trimEnd())
    .filter((l) => l.length > 0)
  if (lines.length < 2) return []
  const headers = parseCsvLine(lines[0]!).map((h) => h.trim())
  const idIdx = headers.indexOf('id')
  if (idIdx < 0) throw new Error('CSV missing id column')

  const trips: TripStub[] = []
  for (const line of lines.slice(1)) {
    const cols = parseCsvLine(line)
    const row: Record<string, string> = {}
    headers.forEach((h, i) => {
      row[h] = cols[i] ?? ''
    })
    if (!row.id) continue
    const num = (k: string) => {
      const v = row[k]
      if (v === undefined || v === '') return null
      const n = Number(v)
      return Number.isFinite(n) ? n : null
    }
    const bool = (k: string) => {
      const v = row[k]
      if (v === undefined || v === '') return undefined
      return v === '1' || v.toLowerCase() === 'true'
    }
    trips.push({
      id: row.id,
      state: row.state || row.status || undefined,
      status: row.status || row.state || undefined,
      start: row.start || undefined,
      end: row.end || null,
      distance_mi: num('distance_mi'),
      duration_s: num('duration_s'),
      duration_min: num('duration_min'),
      avg_speed_mph: num('avg_speed_mph'),
      max_speed_mph: num('max_speed_mph'),
      idle_time_s: num('idle_time_s'),
      fuel_used_pct: num('fuel_used_pct'),
      fuel_estimate_status: row.fuel_estimate_status || undefined,
      efficiency_score: num('efficiency_score'),
      efficiency_status: row.efficiency_status || undefined,
      incomplete: bool('incomplete'),
      simulated: bool('simulated') ?? true,
      revision: num('revision') ?? undefined,
      title: row.title || undefined,
      note: row.note || undefined,
    })
  }
  return trips
}

/** Merge imported trips into existing by stable id (idempotent upsert). */
export function mergeTripsById(
  existing: TripStub[],
  incoming: TripStub[],
): TripStub[] {
  const map = new Map<string, TripStub>()
  for (const t of existing) map.set(t.id, t)
  for (const t of incoming) {
    const prev = map.get(t.id)
    if (!prev) {
      map.set(t.id, t)
      continue
    }
    const prevRev = prev.revision ?? -1
    const nextRev = t.revision ?? -1
    if (nextRev >= prevRev) map.set(t.id, { ...prev, ...t })
  }
  return [...map.values()].sort((a, b) =>
    (b.start ?? '').localeCompare(a.start ?? ''),
  )
}

export function downloadTextFile(
  filename: string,
  contents: string,
  mime: string,
) {
  const blob = new Blob([contents], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
