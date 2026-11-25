import { useEffect, useRef, useState } from 'react'
import { cacheLatestSample } from '../lib/idb'
import type { ConnectionState, TelemetrySample } from '../types'

function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.host
  // Dev: Vite proxies /ws → backend
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

export function useTelemetry() {
  const [sample, setSample] = useState<TelemetrySample | null>(null)
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const lastAt = useRef<number>(0)
  const wsRef = useRef<WebSocket | null>(null)
  const openRef = useRef(false)

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
        setConnection((c) => (c === 'disconnected' ? 'connecting' : c === 'stale' ? c : 'live'))
      }

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as TelemetrySample
          lastAt.current = Date.now()
          setSample(data)
          setConnection(connectionFromSample(data, true))
          void cacheLatestSample(data)
        } catch {
          /* ignore malformed */
        }
      }

      ws.onclose = () => {
        openRef.current = false
        if (cancelled) return
        setConnection('disconnected')
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

  return { sample, connection }
}
