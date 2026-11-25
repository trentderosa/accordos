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
  | 'healthy'
  | 'check_engine'
  | 'misfire'
  | 'overheat'
  | 'low_voltage'

export type HealthSeverity = 'info' | 'warning' | 'critical'
export type TrendStatus = 'ok' | 'watch' | 'alert' | 'unavailable'

export interface DiagnosticCode {
  code: string
  title: string
  summary: string
  common_causes?: string[]
  interpretation: 'code'
  interpretation_note: string
  severity: HealthSeverity
  system: string
  reference_found?: boolean
  status: 'active' | 'historical'
  first_seen?: string | null
  last_seen?: string | null
  source?: string
  simulated?: boolean
}

export interface TelemetryTrend {
  metric: string
  unit: string
  label: string
  latest?: number | null
  baseline?: number | null
  status: TrendStatus
  message: string
  points?: { ts: string; value: number }[]
  hysteresis_note?: string | null
}

export interface HealthAlert {
  id: string
  severity: HealthSeverity
  title: string
  detail: string
  metric?: string | null
  active?: boolean
  simulated?: boolean
}

export interface HealthStatus {
  dtcs: DiagnosticCode[]
  alerts: HealthAlert[]
  trends: TelemetryTrend[]
  active_dtc_count: number
  read_only: boolean
  can_clear_codes: boolean
  simulated: boolean
  disclaimer: string
  note: string
  schema_version?: number
}

export interface MaintenanceReminder {
  id: string
  title: string
  kind: string
  due_label: string
  interval_mi?: number | null
  interval_months?: number | null
  last_service_label?: string | null
  status: 'upcoming' | 'due_soon' | 'overdue' | 'unknown'
  note?: string | null
  simulated?: boolean
  source?: string
}

export interface MaintenanceStatus {
  reminders: MaintenanceReminder[]
  simulated: boolean
  note: string
}

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
