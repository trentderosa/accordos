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

export type TripState =
  | 'idle'
  | 'starting'
  | 'active'
  | 'ending'
  | 'finalized'
  | 'recovered'

export interface TripStub {
  id: string
  title?: string
  start?: string
  end?: string | null
  distance_mi?: number | null
  avg_speed_mph?: number | null
  max_speed_mph?: number | null
  duration_min?: number | null
  duration_s?: number | null
  idle_time_s?: number | null
  idle_time_min?: number | null
  fuel_used_pct?: number | null
  fuel_estimate_status?: string
  efficiency_score?: number | null
  efficiency_confidence?: number | null
  efficiency_status?: string
  incomplete?: boolean
  simulated?: boolean
  status?: string
  state?: TripState | string
  label?: string
  note?: string
  revision?: number | null
}

export type TripListSource = 'live' | 'replica' | 'empty'

export interface ScenarioStatus {
  scenario: ScenarioName | string
  signal_lost?: boolean
  valid?: string[]
  simulated?: boolean
}
