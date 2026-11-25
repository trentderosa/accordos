/** IndexedDB: offline glance + trip replica for Phase 3 sync/export. */

import { openDB, type DBSchema, type IDBPDatabase } from 'idb'
import type { ConnectionState, TelemetrySample, TripStub } from '../types'

export interface CachedSample extends TelemetrySample {
  id?: number
  cachedAt: string
}

export interface GlanceSnapshot {
  sample: TelemetrySample
  connection: ConnectionState
  savedAt: string
}

export interface SyncedTrip extends TripStub {
  id: string
  syncedAt: string
}

export interface TripSyncMeta {
  cursor: string
  lastSyncedAt: string | null
  lastError: string | null
}

interface AccordOSDB extends DBSchema {
  settings: {
    key: string
    value: string
  }
  telemetry_cache: {
    key: number
    value: CachedSample
    indexes: { 'by-cachedAt': string }
  }
  trips: {
    key: string
    value: SyncedTrip
    indexes: { 'by-start': string }
  }
}

const DB_NAME = 'accordos'
const DB_VERSION = 2
const GLANCE_KEY = 'glance_snapshot'
const SYNC_CURSOR_KEY = 'trip_sync_cursor'
const SYNC_AT_KEY = 'trip_sync_at'
const SYNC_ERR_KEY = 'trip_sync_error'
const MAX_CACHE = 50

let dbPromise: Promise<IDBPDatabase<AccordOSDB>> | null = null

export function getDb() {
  if (!dbPromise) {
    dbPromise = openDB<AccordOSDB>(DB_NAME, DB_VERSION, {
      upgrade(db, oldVersion) {
        if (!db.objectStoreNames.contains('settings')) {
          db.createObjectStore('settings')
        }
        if (!db.objectStoreNames.contains('telemetry_cache')) {
          const store = db.createObjectStore('telemetry_cache', {
            keyPath: 'id',
            autoIncrement: true,
          })
          store.createIndex('by-cachedAt', 'cachedAt')
        }
        if (oldVersion < 2 && !db.objectStoreNames.contains('trips')) {
          const trips = db.createObjectStore('trips', { keyPath: 'id' })
          trips.createIndex('by-start', 'start')
        }
      },
    })
  }
  return dbPromise
}

/** Test helper — reset the shared DB promise between suites. */
export function resetDbPromise() {
  dbPromise = null
}

export async function cacheLatestSample(sample: TelemetrySample) {
  const db = await getDb()
  await db.add('telemetry_cache', {
    ...sample,
    cachedAt: new Date().toISOString(),
  })
  const all = await db.getAllKeys('telemetry_cache')
  if (all.length > MAX_CACHE) {
    const toDelete = all.slice(0, all.length - MAX_CACHE)
    await Promise.all(toDelete.map((k) => db.delete('telemetry_cache', k)))
  }
}

export async function getLatestCachedSample(): Promise<CachedSample | null> {
  const db = await getDb()
  const keys = await db.getAllKeys('telemetry_cache')
  if (keys.length === 0) return null
  const last = await db.get('telemetry_cache', keys[keys.length - 1]!)
  return last ?? null
}

export async function saveGlanceSnapshot(
  sample: TelemetrySample,
  connection: ConnectionState,
) {
  const snapshot: GlanceSnapshot = {
    sample,
    connection,
    savedAt: new Date().toISOString(),
  }
  await setSetting(GLANCE_KEY, JSON.stringify(snapshot))
  await cacheLatestSample(sample)
}

export async function getGlanceSnapshot(): Promise<GlanceSnapshot | null> {
  const raw = await getSetting(GLANCE_KEY)
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as GlanceSnapshot
      if (parsed?.sample) return parsed
    } catch {
      /* fall through */
    }
  }
  const cached = await getLatestCachedSample()
  if (!cached) return null
  const { cachedAt, ...rest } = cached
  const sample: TelemetrySample = { ...rest }
  delete (sample as { id?: number }).id
  return {
    sample,
    connection: 'disconnected',
    savedAt: cachedAt,
  }
}

export async function getSetting(key: string): Promise<string | undefined> {
  const db = await getDb()
  return db.get('settings', key)
}

export async function setSetting(key: string, value: string) {
  const db = await getDb()
  await db.put('settings', value, key)
}

export async function upsertSyncedTrip(trip: TripStub): Promise<SyncedTrip> {
  const db = await getDb()
  const row: SyncedTrip = {
    ...trip,
    id: trip.id,
    syncedAt: new Date().toISOString(),
  }
  await db.put('trips', row)
  return row
}

export async function upsertSyncedTrips(trips: TripStub[]): Promise<void> {
  const db = await getDb()
  const tx = db.transaction('trips', 'readwrite')
  const now = new Date().toISOString()
  await Promise.all([
    ...trips.map((trip) =>
      tx.store.put({
        ...trip,
        id: trip.id,
        syncedAt: now,
      }),
    ),
    tx.done,
  ])
}

export async function listSyncedTrips(): Promise<SyncedTrip[]> {
  const db = await getDb()
  const all = await db.getAll('trips')
  return all.sort((a, b) => {
    const as = a.start ?? ''
    const bs = b.start ?? ''
    return bs.localeCompare(as)
  })
}

export async function replaceAllSyncedTrips(trips: TripStub[]): Promise<void> {
  const db = await getDb()
  const tx = db.transaction('trips', 'readwrite')
  await tx.store.clear()
  const now = new Date().toISOString()
  await Promise.all([
    ...trips.map((trip) =>
      tx.store.put({
        ...trip,
        id: trip.id,
        syncedAt: now,
      }),
    ),
    tx.done,
  ])
}

export async function getTripSyncMeta(): Promise<TripSyncMeta> {
  const [cursor, lastSyncedAt, lastError] = await Promise.all([
    getSetting(SYNC_CURSOR_KEY),
    getSetting(SYNC_AT_KEY),
    getSetting(SYNC_ERR_KEY),
  ])
  return {
    cursor: cursor ?? '0',
    lastSyncedAt: lastSyncedAt ?? null,
    lastError: lastError ?? null,
  }
}

export async function setTripSyncMeta(
  partial: Partial<TripSyncMeta>,
): Promise<TripSyncMeta> {
  const current = await getTripSyncMeta()
  const next: TripSyncMeta = {
    cursor: partial.cursor ?? current.cursor,
    lastSyncedAt:
      partial.lastSyncedAt !== undefined
        ? partial.lastSyncedAt
        : current.lastSyncedAt,
    lastError:
      partial.lastError !== undefined ? partial.lastError : current.lastError,
  }
  await setSetting(SYNC_CURSOR_KEY, next.cursor)
  if (next.lastSyncedAt) {
    await setSetting(SYNC_AT_KEY, next.lastSyncedAt)
  }
  if (next.lastError === null) {
    const db = await getDb()
    await db.delete('settings', SYNC_ERR_KEY)
  } else if (next.lastError) {
    await setSetting(SYNC_ERR_KEY, next.lastError)
  }
  return next
}
