import { useCallback, useEffect, useRef, useState } from 'react'
import type { HealthStatus, MaintenanceStatus } from '../types'

const POLL_MS = 4000

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) {
    throw new Error(`${path} → ${res.status}`)
  }
  return (await res.json()) as T
}

export interface UseHealthResult {
  health: HealthStatus | null
  maintenance: MaintenanceStatus | null
  error: string | null
  loading: boolean
  refresh: () => Promise<void>
}

export function useHealth(): UseHealthResult {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [maintenance, setMaintenance] = useState<MaintenanceStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const mounted = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const [h, m] = await Promise.all([
        fetchJson<HealthStatus>('/api/health'),
        fetchJson<MaintenanceStatus>('/api/maintenance'),
      ])
      if (!mounted.current) return
      setHealth(h)
      setMaintenance(m)
      setError(null)
    } catch (err) {
      if (!mounted.current) return
      setError(err instanceof Error ? err.message : 'Health fetch failed')
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void refresh()
    const id = window.setInterval(() => {
      void refresh()
    }, POLL_MS)
    return () => {
      mounted.current = false
      window.clearInterval(id)
    }
  }, [refresh])

  return { health, maintenance, error, loading, refresh }
}
