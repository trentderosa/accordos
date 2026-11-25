import { useCallback, useEffect, useRef, useState } from 'react'
import type { TripListSource, TripStub } from '../types'
import {
  downloadTextFile,
  exportTripsCsv,
  exportTripsJson,
  parseTripsCsv,
  parseTripsJson,
} from '../lib/tripExport'
import {
  loadReplicaTrips,
  pullTripSync,
  restoreTripsLocally,
} from '../lib/tripSync'

const POLL_MS = 5000

export interface UseTripsResult {
  trips: TripStub[]
  source: TripListSource
  lastSyncedAt: string | null
  stale: boolean
  error: string | null
  syncing: boolean
  refresh: () => Promise<void>
  exportJson: () => void
  exportCsv: () => void
  restoreFile: (file: File) => Promise<void>
}

export function useTrips(): UseTripsResult {
  const [trips, setTrips] = useState<TripStub[]>([])
  const [source, setSource] = useState<TripListSource>('empty')
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null)
  const [stale, setStale] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const mounted = useRef(true)

  const applyView = useCallback(
    (view: Awaited<ReturnType<typeof pullTripSync>>) => {
      if (!mounted.current) return
      setTrips(view.trips)
      setSource(view.source)
      setLastSyncedAt(view.lastSyncedAt)
      setStale(view.stale)
      setError(view.error)
    },
    [],
  )

  const refresh = useCallback(async () => {
    setSyncing(true)
    try {
      const view = await pullTripSync()
      applyView(view)
    } finally {
      if (mounted.current) setSyncing(false)
    }
  }, [applyView])

  useEffect(() => {
    mounted.current = true
    let cancelled = false

    const boot = async () => {
      const local = await loadReplicaTrips()
      if (cancelled) return
      applyView(local)
      await refresh()
    }
    void boot()

    const id = window.setInterval(() => {
      void refresh()
    }, POLL_MS)

    return () => {
      cancelled = true
      mounted.current = false
      window.clearInterval(id)
    }
  }, [applyView, refresh])

  const exportJson = useCallback(() => {
    const stamp = new Date().toISOString().slice(0, 10)
    downloadTextFile(
      `accordos-trips-${stamp}.json`,
      exportTripsJson(trips),
      'application/json',
    )
  }, [trips])

  const exportCsv = useCallback(() => {
    const stamp = new Date().toISOString().slice(0, 10)
    downloadTextFile(
      `accordos-trips-${stamp}.csv`,
      exportTripsCsv(trips),
      'text/csv',
    )
  }, [trips])

  const restoreFile = useCallback(
    async (file: File) => {
      const text = await file.text()
      const incoming = file.name.toLowerCase().endsWith('.csv')
        ? parseTripsCsv(text)
        : parseTripsJson(text)
      const view = await restoreTripsLocally(incoming)
      applyView(view)
    },
    [applyView],
  )

  return {
    trips,
    source,
    lastSyncedAt,
    stale,
    error,
    syncing,
    refresh,
    exportJson,
    exportCsv,
    restoreFile,
  }
}
