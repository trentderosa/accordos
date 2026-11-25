export type VehicleMode = 'driving' | 'parked' | 'unknown'
export type Quality = 'good' | 'stale' | 'estimated' | 'unavailable'

export interface TelemetrySample {
  timestamp?: string
  source?: 'simulator' | 'obd'
  quality?: Quality
  speed_mph?: number | null
  rpm?: number | null
  fuel_level_pct?: number | null
  coolant_c?: number | null
  engine_load_pct?: number | null
  voltage_v?: number | null
  mode?: VehicleMode
  simulated?: boolean
  message?: string | null
  label?: string
}

export type ConnectionState = 'connecting' | 'live' | 'stale' | 'disconnected'

export type ScenarioName =
  | 'auto'
  | 'parked'
  | 'idle'
  | 'cruise'
  | 'disconnect'
  | 'recover'

export interface TripStub {
  id: string
  title?: string
  start?: string
  end?: string | null
  distance_mi?: number | null
  avg_speed_mph?: number | null
  max_speed_mph?: number | null
  duration_min?: number | null
  simulated?: boolean
  status?: string
  label?: string
  note?: string
}

export interface ScenarioStatus {
  scenario: ScenarioName | string
  signal_lost?: boolean
  valid?: string[]
  simulated?: boolean
}
