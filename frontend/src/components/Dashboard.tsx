import type { ConnectionState, TelemetrySample, VehicleMode } from '../types'

function fmt(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return n.toFixed(digits)
}

function modeLabel(mode?: VehicleMode): string {
  if (mode === 'driving') return 'DRIVING'
  if (mode === 'parked') return 'PARKED'
  return 'UNCERTAIN'
}

function connectionLabel(c: ConnectionState): string {
  switch (c) {
    case 'live':
      return 'Connected'
    case 'stale':
      return 'Stale data'
    case 'connecting':
      return 'Connecting…'
    default:
      return 'Disconnected'
  }
}

interface Props {
  sample: TelemetrySample | null
  connection: ConnectionState
}

export function Dashboard({ sample, connection }: Props) {
  const mode = sample?.mode ?? 'unknown'
  const driving = mode === 'driving'
  const parked = mode === 'parked'

  return (
    <div className={`dash ${driving ? 'dash--driving' : parked ? 'dash--parked' : 'dash--unknown'}`}>
      <header className="top">
        <div className="brand">
          <span className="brand__name">AccordOS</span>
          <span className="sim-badge" title="Phase 1 uses simulated telemetry only">
            SIMULATED
          </span>
        </div>
        <div className="status-row">
          <span className={`pill pill--mode`}>{modeLabel(mode)}</span>
          <span className={`pill pill--conn pill--${connection}`}>{connectionLabel(connection)}</span>
        </div>
      </header>

      <main className="gauges">
        <div className="gauge gauge--speed">
          <div className="gauge__value">{fmt(sample?.speed_mph, 0)}</div>
          <div className="gauge__unit">mph</div>
        </div>

        <div className="gauge-secondary">
          <div className="gauge gauge--rpm">
            <div className="gauge__value gauge__value--md">{fmt(sample?.rpm, 0)}</div>
            <div className="gauge__unit">RPM</div>
          </div>
          <div className="gauge gauge--fuel">
            <div className="gauge__value gauge__value--md">{fmt(sample?.fuel_level_pct, 0)}</div>
            <div className="gauge__unit">% fuel</div>
          </div>
        </div>
      </main>

      {parked ? (
        <section className="parked-panel">
          <h2>Parked details</h2>
          <p className="lede">Simulated sensors while the cycle is parked. Trip history and health expand in later phases.</p>
          <dl className="metrics">
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
        <section className="trip-strip" aria-label="Current trip">
          <div>
            <span className="muted">Load</span>
            <strong>{fmt(sample?.engine_load_pct, 0)}%</strong>
          </div>
          <div>
            <span className="muted">Coolant</span>
            <strong>{fmt(sample?.coolant_c, 0)}°</strong>
          </div>
          <div>
            <span className="muted">Batt</span>
            <strong>{fmt(sample?.voltage_v, 1)}V</strong>
          </div>
        </section>
      )}

      <footer className="foot">
        <span>{sample?.message ?? 'Waiting for simulator…'}</span>
        <span className="muted">Phase 1 · not a real vehicle</span>
      </footer>
    </div>
  )
}
