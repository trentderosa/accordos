import { Dashboard } from './components/Dashboard'
import { useHealth } from './hooks/useHealth'
import { useScenario } from './hooks/useScenario'
import { useTelemetry } from './hooks/useTelemetry'
import { useTrips } from './hooks/useTrips'
import { useVoice } from './hooks/useVoice'
import './App.css'

export default function App() {
  const { sample, connection, fromCache, cachedAt } = useTelemetry()
  const tripState = useTrips()
  const healthState = useHealth()
  const voice = useVoice()
  const { status, pending, error, setScenario } = useScenario()

  return (
    <Dashboard
      sample={sample}
      connection={connection}
      fromCache={fromCache}
      cachedAt={cachedAt}
      trips={tripState.trips}
      tripSource={tripState.source}
      tripStale={tripState.stale}
      tripLastSyncedAt={tripState.lastSyncedAt}
      onExportJson={tripState.exportJson}
      onExportCsv={tripState.exportCsv}
      onRestoreFile={tripState.restoreFile}
      health={healthState.health}
      maintenance={healthState.maintenance}
      healthError={healthState.error}
      voiceBriefing={voice.briefing}
      voiceSession={voice.session}
      voiceLastResult={voice.lastResult}
      voicePending={voice.pending}
      voiceError={voice.error}
      onVoiceSend={voice.sendText}
      onVoiceRefreshBriefing={voice.refreshBriefing}
      scenario={status?.scenario ?? null}
      scenarioPending={pending}
      scenarioError={error}
      onScenario={setScenario}
    />
  )
}
