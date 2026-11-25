import type { ConnectionState, TelemetrySample, VehicleMode } from '../types'

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

function clampPct(n: number | null | undefined): number {
  if (n === null || n === undefined || Number.isNaN(n)) return 0
  return Math.max(0, Math.min(100, n))
}

/** Soft redline near 6k for visual scale; Phase 1 display only. */
const RPM_SCALE = 7000

interface Props {
  sample: TelemetrySample | null
  connection: ConnectionState
}

export function Dashboard({ sample, connection }: Props) {
  const mode = sample?.mode ?? 'unknown'
  const driving = mode === 'driving'
  const parked = mode === 'parked'
  const rpmPct = clampPct(((sample?.rpm ?? 0) / RPM_SCALE) * 100)
  const fuelPct = clampPct(sample?.fuel_level_pct)

  return (
    <div
      className={`cluster ${driving ? 'cluster--driving' : parked ? 'cluster--parked' : 'cluster--unknown'}`}
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
          <span className={`conn conn--${connection}`}>
            <span className="conn__dot" aria-hidden="true" />
            {connectionLabel(connection)}
          </span>
          <span className={`mode mode--${mode}`}>{modeLabel(mode)}</span>
        </div>
      </header>

      <main className="cluster__stage">
        <div className="speed">
          <div className="speed__value">{fmt(sample?.speed_mph, 0)}</div>
          <div className="speed__unit">mph</div>
        </div>

        <div className="instruments" aria-label="Secondary instruments">
          <div className="instrument">
            <div className="instrument__head">
              <span className="instrument__label">RPM</span>
              <span className="instrument__readout">{fmt(sample?.rpm, 0)}</span>
            </div>
            <div
              className="bar"
              role="meter"
              aria-valuemin={0}
              aria-valuemax={RPM_SCALE}
              aria-valuenow={sample?.rpm ?? 0}
              aria-label="Engine RPM"
            >
              <div className="bar__fill bar__fill--rpm" style={{ width: `${rpmPct}%` }} />
            </div>
          </div>

          <div className="instrument">
            <div className="instrument__head">
              <span className="instrument__label">Fuel</span>
              <span className="instrument__readout">{fmt(sample?.fuel_level_pct, 0)}%</span>
            </div>
            <div
              className="bar"
              role="meter"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={sample?.fuel_level_pct ?? 0}
              aria-label="Fuel level"
            >
              <div className="bar__fill bar__fill--fuel" style={{ width: `${fuelPct}%` }} />
            </div>
          </div>
        </div>
      </main>

      {parked ? (
        <section className="detail" aria-label="Parked details">
          <p className="detail__lede">
            Parked cycle — sensors idle. Trip history and health arrive in later phases.
          </p>
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
        </section>
      ) : (
        <section className="vitals" aria-label="Current vitals">
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
        </section>
      )}

      <footer className="cluster__foot">
        <span>{sample?.message ?? 'Waiting for simulator…'}</span>
        <span className="cluster__foot-meta">Phase 1 · not a real vehicle</span>
      </footer>
    </div>
  )
}
