import { Dashboard } from './components/Dashboard'
import { useTelemetry } from './hooks/useTelemetry'
import './App.css'

export default function App() {
  const { sample, connection } = useTelemetry()
  return <Dashboard sample={sample} connection={connection} />
}
