import { useEffect, useRef, useState } from 'react'
import { getGlanceSnapshot, saveGlanceSnapshot } from '../lib/idb'
import type { ConnectionState, TelemetrySample } from '../types'

function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.host
  // Dev: Vite proxies /ws → backend (works for LAN clients via Mac host)
  return `${proto}://${host}/ws/telemetry`
}

const STALE_MS = 3000

function connectionFromSample(
  data: TelemetrySample,
  socketOpen: boolean,
): ConnectionState {
  if (!socketOpen) return 'disconnected'
  if (data.quality === 'unavailable') return 'disconnected'
  if (data.quality === 'stale') return 'stale'
  return 'live'
}

function asCachedSample(sample: TelemetrySample): TelemetrySample {
  return {
    ...sample,
    quality: sample.quality === 'unavailable' ? 'unavailable' : 'stale',
    message: sample.message
      ? `${sample.message} · cached glance`
      : 'Cached glance — not live',
  }
}

export function useTelemetry() {
  const [sample, setSample] = useState<TelemetrySample | null>(null)
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const [fromCache, setFromCache] = useState(false)
  const [cachedAt, setCachedAt] = useState<string | null>(null)
  const lastAt = useRef<number>(0)
  const wsRef = useRef<WebSocket | null>(null)
  const openRef = useRef(false)
  const hydratedRef = useRef(false)

  useEffect(() => {
    let cancelled = false

    void (async () => {
      try {
        const glance = await getGlanceSnapshot()
        if (cancelled || !glance || hydratedRef.current) return
        // Only apply cache if live stream has not already written
        if (lastAt.current) return
        hydratedRef.current = true
        setSample(asCachedSample(glance.sample))
        setFromCache(true)
        setCachedAt(glance.savedAt)
        setConnection('disconnected')
      } catch {
        /* IndexedDB unavailable — continue without cache */
      }
    })()

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    let retry: ReturnType<typeof setTimeout> | undefined
    let staleTimer: ReturnType<typeof setInterval> | undefined

    const connect = () => {
      if (cancelled) return
      openRef.current = false
      setConnection((c) => (c === 'live' ? c : 'connecting'))
      const ws = new WebSocket(wsUrl())
      wsRef.current = ws

      ws.onopen = () => {
        if (cancelled) return
        openRef.current = true
        setConnection((c) =>
          c === 'disconnected' ? 'connecting' : c === 'stale' ? c : 'live',
        )
      }

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as TelemetrySample
          lastAt.current = Date.now()
          hydratedRef.current = true
          setSample(data)
          setFromCache(false)
          setCachedAt(null)
          const next = connectionFromSample(data, true)
          setConnection(next)
          if (data.quality !== 'unavailable') {
            void saveGlanceSnapshot(data, next)
          }
        } catch {
          /* ignore malformed */
        }
      }

      ws.onclose = () => {
        openRef.current = false
        if (cancelled) return
        setConnection('disconnected')
        // Keep last sample visible as an honest cached glance
        setFromCache(true)
        setCachedAt(new Date().toISOString())
        setSample((s) => (s ? asCachedSample(s) : s))
        retry = setTimeout(connect, 1500)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()

    staleTimer = setInterval(() => {
      if (!lastAt.current) return
      if (!openRef.current) return
      if (Date.now() - lastAt.current > STALE_MS) {
        setConnection((c) => (c === 'disconnected' ? c : 'stale'))
        setSample((s) =>
          s && s.quality !== 'stale' && s.quality !== 'unavailable'
            ? { ...s, quality: 'stale' }
            : s,
        )
      }
    }, 500)

    return () => {
      cancelled = true
      if (retry) clearTimeout(retry)
      if (staleTimer) clearInterval(staleTimer)
      wsRef.current?.close()
    }
  }, [])

  return { sample, connection, fromCache, cachedAt }
}
