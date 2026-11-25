/** Client for Pi-authoritative GET /api/sync + IndexedDB replica. */

import type { TripStub } from '../types'
import {
  getTripSyncMeta,
  listSyncedTrips,
  replaceAllSyncedTrips,
  setTripSyncMeta,
  upsertSyncedTrips,
} from './idb'
import { mergeTripsById } from './tripExport'

export interface SyncRevision {
  revision: number
  op: string
  entity: string
  id: string
  trip: TripStub
}

export interface SyncPage {
  cursor: string
  next_cursor: string
  has_more: boolean
  page_size: number
  revisions: SyncRevision[]
  semantics?: Record<string, unknown>
  note?: string
}

export type TripSource = 'live' | 'replica' | 'empty'

export interface TripsViewState {
  trips: TripStub[]
  source: TripSource
  syncCursor: string
  lastSyncedAt: string | null
  stale: boolean
  error: string | null
}

export function applySyncRevisions(
  existing: TripStub[],
  revisions: SyncRevision[],
): TripStub[] {
  const incoming = revisions
    .filter((r) => r.op === 'upsert' && r.trip?.id)
    .map((r) => ({ ...r.trip, id: r.id || r.trip.id, revision: r.revision }))
  return mergeTripsById(existing, incoming)
}

async function fetchSyncPage(
  cursor: string,
  limit = 50,
): Promise<SyncPage> {
  const params = new URLSearchParams({
    cursor,
    limit: String(limit),
  })
  const res = await fetch(`/api/sync?${params}`)
  if (!res.ok) {
    throw new Error(`Sync failed (${res.status})`)
  }
  return (await res.json()) as SyncPage
}

/** Pull all pages from the current cursor; upsert into IndexedDB. */
export async function pullTripSync(): Promise<TripsViewState> {
  const meta = await getTripSyncMeta()
  let cursor = meta.cursor || '0'
  let existing: TripStub[] = await listSyncedTrips()
  let pulled = 0

  try {
    while (true) {
      const page = await fetchSyncPage(cursor)
      if (page.revisions?.length) {
        existing = applySyncRevisions(existing, page.revisions)
        await upsertSyncedTrips(
          page.revisions.map((r) => ({
            ...r.trip,
            id: r.id,
            revision: r.revision,
          })),
        )
        pulled += page.revisions.length
      }
      cursor = page.next_cursor
      if (!page.has_more) break
      if (pulled > 5000) break
    }

    const now = new Date().toISOString()
    await setTripSyncMeta({
      cursor,
      lastSyncedAt: now,
      lastError: null,
    })
    const trips = await listSyncedTrips()
    return {
      trips,
      source: trips.length ? 'live' : 'empty',
      syncCursor: cursor,
      lastSyncedAt: now,
      stale: false,
      error: null,
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Sync unavailable'
    await setTripSyncMeta({ lastError: message })
    const trips = await listSyncedTrips()
    const hadSync = Boolean(meta.lastSyncedAt) || trips.length > 0
    return {
      trips,
      source: trips.length ? 'replica' : 'empty',
      syncCursor: meta.cursor,
      lastSyncedAt: meta.lastSyncedAt,
      stale: hadSync,
      error: message,
    }
  }
}

export async function loadReplicaTrips(): Promise<TripsViewState> {
  const [trips, meta] = await Promise.all([
    listSyncedTrips(),
    getTripSyncMeta(),
  ])
  return {
    trips,
    source: trips.length ? 'replica' : 'empty',
    syncCursor: meta.cursor,
    lastSyncedAt: meta.lastSyncedAt,
    stale: Boolean(meta.lastSyncedAt),
    error: meta.lastError,
  }
}

export async function restoreTripsLocally(
  incoming: TripStub[],
): Promise<TripsViewState> {
  const existing = await listSyncedTrips()
  const merged = mergeTripsById(existing, incoming)
  await replaceAllSyncedTrips(merged)
  const meta = await getTripSyncMeta()
  return {
    trips: merged,
    source: merged.length ? 'replica' : 'empty',
    syncCursor: meta.cursor,
    lastSyncedAt: meta.lastSyncedAt,
    stale: true,
    error: null,
  }
}
