import { Dashboard } from './components/Dashboard'
import { useScenario } from './hooks/useScenario'
import { useTelemetry } from './hooks/useTelemetry'
import { useTrips } from './hooks/useTrips'
import './App.css'

export default function App() {
  const { sample, connection } = useTelemetry()
  const trips = useTrips()
  const { status, pending, error, setScenario } = useScenario()

  return (
    <Dashboard
      sample={sample}
      connection={connection}
      trips={trips}
      scenario={status?.scenario ?? null}
      scenarioPending={pending}
      scenarioError={error}
      onScenario={setScenario}
    />
  )
}
