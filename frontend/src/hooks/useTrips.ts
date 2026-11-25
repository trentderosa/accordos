import { useCallback, useEffect, useState } from 'react'
import type { TripStub } from '../types'

const POLL_MS = 4000

export function useTrips() {
  const [trips, setTrips] = useState<TripStub[]>([])

  const load = useCallback(async () => {
    try {
      const res = await fetch('/api/trips')
      if (!res.ok) return
      const body = (await res.json()) as { trips?: TripStub[] }
      setTrips(body.trips ?? [])
    } catch {
      /* offline / backend down — keep last known list */
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      if (cancelled) return
      await load()
    }
    void tick()
    const id = window.setInterval(() => {
      void tick()
    }, POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [load])

  return trips
}
