import { useRef } from 'react'
import type {
  ConnectionState,
  HealthStatus,
  MaintenanceStatus,
  ScenarioName,
  TelemetrySample,
  TripListSource,
  TripStub,
  VehicleMode,
  VoiceBriefing,
  VoiceCommandResult,
  VoiceSessionInfo,
} from '../types'
import { VoiceLab } from './VoiceLab'

function fmt(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return n.toFixed(digits)
}

function modeLabel(mode?: VehicleMode): string {
  if (mode === 'driving') return 'Driving'
  if (mode === 'parked') return 'Parked'
  return 'Uncertain'
}

function connectionLabel(c: ConnectionState): string {
  switch (c) {
    case 'live':
      return 'Live'
    case 'stale':
      return 'Stale'
    case 'connecting':
      return 'Connecting'
    default:
      return 'Offline'
  }
}

function shortCacheWhen(iso?: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function connectionBanner(
  c: ConnectionState,
  sample: TelemetrySample | null,
  fromCache: boolean,
  cachedAt: string | null,
): {
  title: string
  detail: string
} | null {
  if (c === 'live') return null
  if (c === 'connecting' && !fromCache) {
    return {
      title: 'Connecting',
      detail: 'Waiting for telemetry stream…',
    }
  }
  if (c === 'stale' && !fromCache) {
    return {
      title: 'Stale data',
      detail: 'Last reading is aging — gauges may lag.',
    }
  }
  if (fromCache && sample && sample.quality !== 'unavailable') {
    const when = shortCacheWhen(cachedAt)
    return {
      title: 'Cached glance',
      detail: when
        ? `Not live — showing last saved reading (${when}).`
        : 'Not live — showing last saved reading from this device.',
    }
  }
  if (c === 'connecting') {
    return {
      title: 'Connecting',
      detail: 'Waiting for telemetry stream…',
    }
  }
  if (c === 'stale') {
    return {
      title: 'Stale data',
      detail: 'Last reading is aging — gauges may lag.',
    }
  }
  const simulatedLoss = sample?.quality === 'unavailable' && sample?.simulated
  return {
    title: simulatedLoss ? 'Signal lost' : 'Disconnected',
    detail: simulatedLoss
      ? 'SIMULATED disconnect — recover to restore stream.'
      : 'Link down — retrying quietly in the background.',
  }
}

function clampPct(n: number | null | undefined): number {
  if (n === null || n === undefined || Number.isNaN(n)) return 0
  return Math.max(0, Math.min(100, n))
}

function shortWhen(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/** Soft redline near 6k for visual scale; Phase 1 display only. */
const RPM_SCALE = 7000

const SCENARIO_BUTTONS: { id: ScenarioName; label: string }[] = [
  { id: 'idle', label: 'Idle' },
  { id: 'cruise', label: 'Cruise' },
  { id: 'disconnect', label: 'Disconnect' },
  { id: 'recover', label: 'Recover' },
  { id: 'parked', label: 'Parked' },
  { id: 'auto', label: 'Auto' },
  { id: 'healthy', label: 'Healthy' },
  { id: 'check_engine', label: 'P0420' },
  { id: 'misfire', label: 'Misfire' },
  { id: 'overheat', label: 'Overheat' },
  { id: 'low_voltage', label: 'Low V' },
]

interface Props {
  sample: TelemetrySample | null
  connection: ConnectionState
  fromCache?: boolean
  cachedAt?: string | null
  trips: TripStub[]
  tripSource?: TripListSource
  tripStale?: boolean
  tripLastSyncedAt?: string | null
  onExportJson?: () => void
  onExportCsv?: () => void
  onRestoreFile?: (file: File) => Promise<void>
  health?: HealthStatus | null
  maintenance?: MaintenanceStatus | null
  healthError?: string | null
  voiceBriefing?: VoiceBriefing | null
  voiceSession?: VoiceSessionInfo | null
  voiceLastResult?: VoiceCommandResult | null
  voicePending?: boolean
  voiceError?: string | null
  onVoiceSend?: (text: string) => Promise<unknown>
  onVoiceRefreshBriefing?: () => void
  scenario: string | null
  scenarioPending: boolean
  scenarioError: string | null
  onScenario: (name: ScenarioName) => void
}

export function Dashboard({
  sample,
  connection,
  fromCache = false,
  cachedAt = null,
  trips,
  tripSource = 'empty',
  tripStale = false,
  tripLastSyncedAt = null,
  onExportJson,
  onExportCsv,
  onRestoreFile,
  health = null,
  maintenance = null,
  healthError = null,
  voiceBriefing = null,
  voiceSession = null,
  voiceLastResult = null,
  voicePending = false,
  voiceError = null,
  onVoiceSend,
  onVoiceRefreshBriefing,
  scenario,
  scenarioPending,
  scenarioError,
  onScenario,
}: Props) {
  const restoreInputRef = useRef<HTMLInputElement>(null)
  const mode = sample?.mode ?? 'unknown'
  const driving = mode === 'driving'
  const parked = mode === 'parked'
  const noLiveSignal =
    connection === 'disconnected' || sample?.quality === 'unavailable'
  // Cached offline glance still shows last numbers — only blank for true no-data signal loss
  const signalDown = noLiveSignal && !(fromCache && sample && sample.quality !== 'unavailable')
  const showCachedGauges = Boolean(fromCache && sample && sample.quality !== 'unavailable')
  // Parked history stays available from IndexedDB replica when the backend is offline.
  const showParked =
    (parked && !signalDown) ||
    (parked && showCachedGauges) ||
    (showCachedGauges && (trips.length > 0 || tripSource === 'replica'))
  const rpmPct = clampPct(((sample?.rpm ?? 0) / RPM_SCALE) * 100)
  const fuelPct = clampPct(sample?.fuel_level_pct)
  const banner = connectionBanner(connection, sample, fromCache, cachedAt)
  const activeScenario = scenario ?? 'auto'

  const tripBadge =
    tripSource === 'live'
      ? 'Synced'
      : tripSource === 'replica'
        ? tripStale
          ? 'Offline replica'
          : 'Replica'
        : trips.length === 0 && !tripLastSyncedAt
          ? 'Waiting'
          : 'Empty'

  const emptyTripsMessage = (() => {
    if (!tripLastSyncedAt && tripSource === 'empty') {
      return 'No trips yet — run Auto or Cruise, then Parked to finalize a simulated drive.'
    }
    if (tripStale || tripSource === 'replica') {
      return 'No trips in the local replica. Export/restore if iOS cleared storage, or reconnect to sync.'
    }
    return 'No completed trips on this device.'
  })()

  return (
    <div
      className={[
        'cluster',
        driving ? 'cluster--driving' : parked ? 'cluster--parked' : 'cluster--unknown',
        signalDown ? 'cluster--offline' : '',
        connection === 'stale' || showCachedGauges ? 'cluster--stale' : '',
        showCachedGauges ? 'cluster--cached' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <div className="cluster__ambient" aria-hidden="true" />

      <header className="cluster__chrome">
        <div className="wordmark">
          <span className="wordmark__name">AccordOS</span>
          <span className="wordmark__vehicle">2014 Honda Accord</span>
        </div>

        <div className="chrome-status" aria-label="System status">
          <span className="sim-tag" title="Phase 1 uses simulated telemetry only">
            SIMULATED
          </span>
          <span
            className={`conn conn--${showCachedGauges ? 'stale' : connection}`}
          >
            <span className="conn__dot" aria-hidden="true" />
            {showCachedGauges ? 'Cached' : connectionLabel(connection)}
          </span>
          <span className={`mode mode--${mode}`}>{modeLabel(mode)}</span>
        </div>
      </header>

      {banner ? (
        <div
          className={`link-banner link-banner--${connection}`}
          role="status"
          aria-live="polite"
        >
          <span className="link-banner__title">{banner.title}</span>
          <span className="link-banner__detail">{banner.detail}</span>
        </div>
      ) : null}

      <main className="cluster__stage">
        <div
          className={`speed ${signalDown || showCachedGauges ? 'speed--muted' : ''}`}
        >
          <div className={`speed__value ${signalDown ? 'speed__value--offline' : ''}`}>
            {signalDown ? 'NO SIGNAL' : fmt(sample?.speed_mph, 0)}
          </div>
          <div className="speed__unit">
            {showCachedGauges ? 'mph · cached' : 'mph'}
          </div>
        </div>

        <div className="instruments" aria-label="Secondary instruments">
          <div className="instrument">
            <div className="instrument__head">
              <span className="instrument__label">RPM</span>
              <span className="instrument__readout">
                {signalDown ? '—' : fmt(sample?.rpm, 0)}
              </span>
            </div>
            <div
              className="bar"
              role="meter"
              aria-valuemin={0}
              aria-valuemax={RPM_SCALE}
              aria-valuenow={signalDown ? 0 : (sample?.rpm ?? 0)}
              aria-label="Engine RPM"
            >
              <div
                className="bar__fill bar__fill--rpm"
                style={{ width: `${signalDown ? 0 : rpmPct}%` }}
              />
            </div>
          </div>

          <div className="instrument">
            <div className="instrument__head">
              <span className="instrument__label">Fuel</span>
              <span className="instrument__readout">
                {signalDown ? '—' : `${fmt(sample?.fuel_level_pct, 0)}%`}
              </span>
            </div>
            <div
              className="bar"
              role="meter"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={signalDown ? 0 : (sample?.fuel_level_pct ?? 0)}
              aria-label="Fuel level"
            >
              <div
                className="bar__fill bar__fill--fuel"
                style={{ width: `${signalDown ? 0 : fuelPct}%` }}
              />
            </div>
          </div>
        </div>
      </main>

      {showParked ? (
        <section className="parked" aria-label="Parked details">
          <div className="parked__intro">
            <h2 className="parked__title">Parked</h2>
            <p className="parked__lede">
              Engine off confirmed by the simulator cycle — not inferred from 0 mph alone.
              Recent trips sync from the Pi journal into this device; offline reads use the local replica.
            </p>
          </div>

          {!signalDown || showCachedGauges ? (
            <dl className="detail__grid">
              <div>
                <dt>Coolant</dt>
                <dd>{fmt(sample?.coolant_c, 1)} °C</dd>
              </div>
              <div>
                <dt>Voltage</dt>
                <dd>{fmt(sample?.voltage_v, 1)} V</dd>
              </div>
              <div>
                <dt>Engine load</dt>
                <dd>{fmt(sample?.engine_load_pct, 0)} %</dd>
              </div>
              <div>
                <dt>Quality</dt>
                <dd>{sample?.quality ?? '—'}</dd>
              </div>
            </dl>
          ) : null}

          <div className="parked__history">
            <div className="parked__history-head">
              <span>Recent trips</span>
              <span className="parked__badge">{tripBadge}</span>
            </div>
            {tripStale && tripLastSyncedAt ? (
              <p className="parked__sync-note">
                Last sync {shortCacheWhen(tripLastSyncedAt)}
                {tripSource === 'replica' ? ' · showing local replica' : ''}
              </p>
            ) : tripSource === 'live' && tripLastSyncedAt ? (
              <p className="parked__sync-note">
                Synced {shortCacheWhen(tripLastSyncedAt)}
              </p>
            ) : null}
            {trips.length === 0 ? (
              <p className="parked__empty">{emptyTripsMessage}</p>
            ) : (
              <ul className="trip-list">
                {trips.map((t) => (
                  <li key={t.id} className="trip-list__item">
                    <div className="trip-list__row">
                      <span className="trip-list__title">
                        {t.title ?? (t.status === 'recovered' ? 'Recovered trip' : 'Trip')}
                      </span>
                      <span className="trip-list__meta">
                        {fmt(t.distance_mi, 1)} mi · {fmt(t.duration_min, 0)} min
                        {t.incomplete ? ' · incomplete' : ''}
                      </span>
                    </div>
                    <div className="trip-list__when">
                      {shortWhen(t.start)}
                      {t.efficiency_status === 'available' && t.efficiency_score != null
                        ? ` · efficiency ${fmt(t.efficiency_score, 0)}`
                        : t.efficiency_status === 'withheld'
                          ? ' · efficiency withheld'
                          : ''}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <div className="parked__export">
              <button
                type="button"
                className="quiet-link"
                onClick={() => onExportJson?.()}
                disabled={!onExportJson || trips.length === 0}
              >
                Export JSON
              </button>
              <span className="parked__export-sep" aria-hidden="true">
                ·
              </span>
              <button
                type="button"
                className="quiet-link"
                onClick={() => onExportCsv?.()}
                disabled={!onExportCsv || trips.length === 0}
              >
                Export CSV
              </button>
              <span className="parked__export-sep" aria-hidden="true">
                ·
              </span>
              <button
                type="button"
                className="quiet-link"
                onClick={() => restoreInputRef.current?.click()}
                disabled={!onRestoreFile}
              >
                Restore
              </button>
              <input
                ref={restoreInputRef}
                type="file"
                accept=".json,.csv,application/json,text/csv"
                className="parked__file"
                aria-label="Restore trip history"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  e.target.value = ''
                  if (file && onRestoreFile) void onRestoreFile(file)
                }}
              />
            </div>
          </div>

          <div className="parked__health" aria-label="Vehicle health">
            <div className="parked__history-head">
              <span>Vehicle health</span>
              <span className="parked__badge">
                {health?.active_dtc_count
                  ? `${health.active_dtc_count} active`
                  : 'Read-only'}
              </span>
            </div>
            <p className="parked__health-disclaimer">
              {health?.disclaimer ??
                'Codes are fault flags — not confirmed diagnoses. Factory warnings remain authoritative. AccordOS never clears codes.'}
            </p>
            {healthError ? (
              <p className="parked__empty">{healthError}</p>
            ) : null}

            {health?.alerts && health.alerts.length > 0 ? (
              <ul className="health-alerts">
                {health.alerts.map((a) => (
                  <li
                    key={a.id}
                    className={`health-alerts__item health-alerts__item--${a.severity}`}
                  >
                    <span className="health-alerts__title">{a.title}</span>
                    <span className="health-alerts__detail">{a.detail}</span>
                  </li>
                ))}
              </ul>
            ) : null}

            <div className="health-dtcs">
              <div className="parked__history-head">
                <span>Diagnostic codes</span>
                <span className="parked__badge">
                  {health?.can_clear_codes === false ? 'No clear' : ''}
                </span>
              </div>
              {!health?.dtcs?.length ? (
                <p className="parked__empty">
                  No codes reported — absence of codes is not a clean bill of health.
                </p>
              ) : (
                <ul className="dtc-list">
                  {health.dtcs.map((d) => (
                    <li key={`${d.code}-${d.status}-${d.first_seen ?? ''}`} className="dtc-list__item">
                      <div className="dtc-list__row">
                        <span className={`dtc-list__code dtc-list__code--${d.severity}`}>
                          {d.code}
                        </span>
                        <span className="dtc-list__status">{d.status}</span>
                      </div>
                      <div className="dtc-list__title">{d.title}</div>
                      <p className="dtc-list__summary">{d.summary}</p>
                      <p className="dtc-list__note">{d.interpretation_note}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {health?.trends && health.trends.length > 0 ? (
              <div className="health-trends">
                <div className="parked__history-head">
                  <span>Telemetry trends</span>
                </div>
                <ul className="trend-list">
                  {health.trends.map((t) => {
                    const pts = t.points ?? []
                    const max = Math.max(...pts.map((p) => p.value), 1)
                    const min = Math.min(...pts.map((p) => p.value), 0)
                    const span = Math.max(max - min, 0.01)
                    return (
                      <li key={t.metric} className="trend-list__item">
                        <div className="trend-list__row">
                          <span className="trend-list__label">{t.label}</span>
                          <span className={`trend-list__status trend-list__status--${t.status}`}>
                            {t.status}
                          </span>
                        </div>
                        <div className="trend-list__readout">
                          {t.latest != null ? `${fmt(t.latest, 1)} ${t.unit}` : '—'}
                          {t.baseline != null ? (
                            <span className="trend-list__base">
                              {' '}
                              · baseline {fmt(t.baseline, 1)}
                            </span>
                          ) : null}
                        </div>
                        {pts.length > 1 ? (
                          <div
                            className="spark"
                            role="img"
                            aria-label={`${t.label} recent trend`}
                          >
                            {pts.map((p, i) => (
                              <span
                                key={`${p.ts}-${i}`}
                                className="spark__bar"
                                style={{
                                  height: `${8 + ((p.value - min) / span) * 22}px`,
                                }}
                              />
                            ))}
                          </div>
                        ) : null}
                        <p className="trend-list__msg">{t.message}</p>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ) : null}

            <div className="health-maint">
              <div className="parked__history-head">
                <span>Maintenance</span>
                <span className="parked__badge">Intervals</span>
              </div>
              <p className="parked__sync-note">
                {maintenance?.note ??
                  'Reminders use owner intervals — not fabricated odometer readings.'}
              </p>
              {!maintenance?.reminders?.length ? (
                <p className="parked__empty">No reminders configured.</p>
              ) : (
                <ul className="maint-list">
                  {maintenance.reminders.map((r) => (
                    <li key={r.id} className="maint-list__item">
                      <div className="maint-list__row">
                        <span className="maint-list__title">{r.title}</span>
                        <span className={`maint-list__status maint-list__status--${r.status}`}>
                          {r.status.replace('_', ' ')}
                        </span>
                      </div>
                      <div className="maint-list__due">{r.due_label}</div>
                      {r.last_service_label ? (
                        <div className="maint-list__last">{r.last_service_label}</div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {onVoiceSend ? (
              <VoiceLab
                briefing={voiceBriefing}
                session={voiceSession}
                lastResult={voiceLastResult}
                pending={voicePending}
                error={voiceError}
                onSend={onVoiceSend}
                onRefreshBriefing={onVoiceRefreshBriefing}
              />
            ) : null}
          </div>
        </section>
      ) : mode === 'unknown' && !signalDown ? (
        <section className="uncertain" aria-label="Uncertain status">
          <p className="uncertain__lede">
            Speed is zero but parked is not assumed — waiting for clearer engine-off evidence.
          </p>
          <div className="vitals vitals--inline" aria-label="Current vitals">
            <div>
              <span className="vitals__label">Load</span>
              <span className="vitals__value">{fmt(sample?.engine_load_pct, 0)}%</span>
            </div>
            <div>
              <span className="vitals__label">Coolant</span>
              <span className="vitals__value">{fmt(sample?.coolant_c, 0)}°</span>
            </div>
            <div>
              <span className="vitals__label">Batt</span>
              <span className="vitals__value">{fmt(sample?.voltage_v, 1)}V</span>
            </div>
            <div>
              <span className="vitals__label">RPM</span>
              <span className="vitals__value">{fmt(sample?.rpm, 0)}</span>
            </div>
          </div>
        </section>
      ) : (
        <section className="vitals" aria-label="Current vitals">
          <div>
            <span className="vitals__label">Load</span>
            <span className="vitals__value">
              {signalDown ? '—' : `${fmt(sample?.engine_load_pct, 0)}%`}
            </span>
          </div>
          <div>
            <span className="vitals__label">Coolant</span>
            <span className="vitals__value">
              {signalDown ? '—' : `${fmt(sample?.coolant_c, 0)}°`}
            </span>
          </div>
          <div>
            <span className="vitals__label">Batt</span>
            <span className="vitals__value">
              {signalDown ? '—' : `${fmt(sample?.voltage_v, 1)}V`}
            </span>
          </div>
        </section>
      )}

      <section className="scenarios" aria-label="Simulator scenarios">
        <div className="scenarios__head">
          <span>Demo scenarios</span>
          <span className="scenarios__active">{activeScenario}</span>
        </div>
        <div className="scenarios__row">
          {SCENARIO_BUTTONS.map((btn) => (
            <button
              key={btn.id}
              type="button"
              className={`scenario-btn ${activeScenario === btn.id ? 'scenario-btn--active' : ''}`}
              disabled={scenarioPending}
              onClick={() => onScenario(btn.id)}
            >
              {btn.label}
            </button>
          ))}
        </div>
        {scenarioError ? <p className="scenarios__error">{scenarioError}</p> : null}
      </section>

      <footer className="cluster__foot">
        <span>{sample?.message ?? 'Waiting for simulator…'}</span>
        <span className="cluster__foot-meta">
          Health · voice lab · trip journal · not a real vehicle
        </span>
      </footer>
    </div>
  )
}
