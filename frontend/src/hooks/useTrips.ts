import { useEffect, useState } from 'react'
import type { TripStub } from '../types'

export function useTrips() {
  const [trips, setTrips] = useState<TripStub[]>([])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const res = await fetch('/api/trips')
        if (!res.ok) return
        const body = (await res.json()) as { trips?: TripStub[] }
        if (!cancelled) setTrips(body.trips ?? [])
      } catch {
        /* offline / backend down — keep empty placeholders */
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [])

  return trips
}
