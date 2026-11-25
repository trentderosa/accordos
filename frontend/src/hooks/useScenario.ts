import { useCallback, useEffect, useState } from 'react'
import type { ScenarioName, ScenarioStatus } from '../types'

const DEMO_FLOW: ScenarioName[] = ['idle', 'cruise', 'disconnect', 'recover']

export function useScenario() {
  const [status, setStatus] = useState<ScenarioStatus | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res = await fetch('/api/simulator/scenario')
      if (!res.ok) return
      const body = (await res.json()) as ScenarioStatus
      setStatus(body)
      setError(null)
    } catch {
      /* ignore — controls stay usable when backend returns */
    }
  }, [])

  useEffect(() => {
    void refresh()
    // Keep button highlight in sync when scenarios are forced via API/curl.
    const timer = setInterval(() => {
      void refresh()
    }, 1500)
    return () => clearInterval(timer)
  }, [refresh])

  const setScenario = useCallback(
    async (scenario: ScenarioName) => {
      setPending(true)
      setError(null)
      try {
        const res = await fetch('/api/simulator/scenario', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scenario }),
        })
        const body = await res.json()
        if (!res.ok) {
          setError(typeof body?.detail === 'string' ? body.detail : 'Scenario failed')
          return
        }
        setStatus(body as ScenarioStatus)
      } catch {
        setError('Could not reach simulator')
      } finally {
        setPending(false)
      }
    },
    [],
  )

  return { status, pending, error, setScenario, refresh, demoFlow: DEMO_FLOW }
}
