/** IndexedDB scaffold for offline telemetry / trip cache (Phase 3 sync fills this in). */

import { openDB, type DBSchema, type IDBPDatabase } from 'idb'
import type { TelemetrySample } from '../types'

interface CachedSample extends TelemetrySample {
  id?: number
  cachedAt: string
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
}

const DB_NAME = 'accordos'
const DB_VERSION = 1

let dbPromise: Promise<IDBPDatabase<AccordOSDB>> | null = null

export function getDb() {
  if (!dbPromise) {
    dbPromise = openDB<AccordOSDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
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
      },
    })
  }
  return dbPromise
}

export async function cacheLatestSample(sample: TelemetrySample) {
  const db = await getDb()
  await db.add('telemetry_cache', {
    ...sample,
    cachedAt: new Date().toISOString(),
  })
  const all = await db.getAllKeys('telemetry_cache')
  if (all.length > 50) {
    const toDelete = all.slice(0, all.length - 50)
    await Promise.all(toDelete.map((k) => db.delete('telemetry_cache', k)))
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
