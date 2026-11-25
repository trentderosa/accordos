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
