import { useCallback, useEffect, useRef, useState } from 'react'
import type { VoiceBriefing, VoiceCommandResult, VoiceSessionInfo } from '../types'

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    let detail = `${path} → ${res.status}`
    try {
      const body = (await res.json()) as { detail?: string }
      if (body?.detail) detail = String(body.detail)
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return (await res.json()) as T
}

export interface UseVoiceResult {
  briefing: VoiceBriefing | null
  session: VoiceSessionInfo | null
  lastResult: VoiceCommandResult | null
  pending: boolean
  error: string | null
  sendText: (text: string) => Promise<VoiceCommandResult | null>
  refreshBriefing: () => Promise<void>
}

export function useVoice(): UseVoiceResult {
  const [briefing, setBriefing] = useState<VoiceBriefing | null>(null)
  const [session, setSession] = useState<VoiceSessionInfo | null>(null)
  const [lastResult, setLastResult] = useState<VoiceCommandResult | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const mounted = useRef(true)

  const refreshBriefing = useCallback(async () => {
    try {
      const [b, s] = await Promise.all([
        fetchJson<VoiceBriefing>('/api/voice/briefing'),
        fetchJson<VoiceSessionInfo>('/api/voice/session'),
      ])
      if (!mounted.current) return
      setBriefing(b)
      setSession(s)
      setError(null)
    } catch (err) {
      if (!mounted.current) return
      setError(err instanceof Error ? err.message : 'Voice fetch failed')
    }
  }, [])

  const sendText = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return null
    setPending(true)
    setError(null)
    try {
      const result = await fetchJson<VoiceCommandResult>('/api/voice/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: trimmed }),
      })
      if (!mounted.current) return result
      setLastResult(result)
      if (result.session) {
        const sessionState = result.session
        setSession((prev) => ({
          supported_intents: prev?.supported_intents ?? [],
          followup_timeout_s: prev?.followup_timeout_s ?? 15,
          audio_feasibility_gate: prev?.audio_feasibility_gate ?? 'open',
          note: prev?.note ?? '',
          session: sessionState,
        }))
      }
      return result
    } catch (err) {
      if (mounted.current) {
        setError(err instanceof Error ? err.message : 'Voice command failed')
      }
      return null
    } finally {
      if (mounted.current) setPending(false)
    }
  }, [])

  useEffect(() => {
    mounted.current = true
    void refreshBriefing()
    return () => {
      mounted.current = false
    }
  }, [refreshBriefing])

  return {
    briefing,
    session,
    lastResult,
    pending,
    error,
    sendText,
    refreshBriefing,
  }
}
