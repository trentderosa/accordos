import { useRef } from 'react'
import type {
  ConnectionState,
  ScenarioName,
  TelemetrySample,
  TripListSource,
  TripStub,
  VehicleMode,
} from '../types'

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
        <span className="cluster__foot-meta">Trip journal · not a real vehicle</span>
      </footer>
    </div>
  )
}
