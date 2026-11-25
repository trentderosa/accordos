import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { mapsDeepLinks } from '../lib/mapsLinks'
import {
  SPOTIFY_SIRI_HINT,
  openSpotifyFallback,
  spotifyOpenUrl,
} from '../lib/spotifyStub'

/**
 * Parked-only (or clearly labeled) external app shortcuts.
 * Never invents map incidents or Spotify playback state.
 */
interface Props {
  /** When false, show a labeled stub strip instead of interactive launchers. */
  parked: boolean
  /** Optional saved home label — never a fabricated GPS fix. */
  homeLabel?: string
}

export function InfotainmentShortcuts({
  parked,
  homeLabel = 'Home',
}: Props) {
  const [destination, setDestination] = useState(homeLabel)
  const links = useMemo(() => {
    try {
      return mapsDeepLinks(destination || homeLabel)
    } catch {
      return mapsDeepLinks(homeLabel)
    }
  }, [destination, homeLabel])

  function onNavigateSubmit(e: FormEvent) {
    e.preventDefault()
  }

  if (!parked) {
    return (
      <section className="infotainment infotainment--driving" aria-label="Infotainment">
        <p className="infotainment__driving-note">
          Maps &amp; Spotify shortcuts are parked-only — use Waze, Apple Maps, or
          Spotify on the phone while driving.
        </p>
      </section>
    )
  }

  return (
    <section className="infotainment" aria-label="Infotainment shortcuts">
      <div className="infotainment__head">
        <div>
          <h2 className="infotainment__title">Navigate &amp; music</h2>
          <p className="infotainment__lede">
            External deep links only — no embedded map, no live traffic or police
            data in AccordOS. Spotify is open/Siri fallback; core cluster works
            without it.
          </p>
        </div>
        <span className="parked__badge">Parked</span>
      </div>

      <form className="infotainment__form" onSubmit={onNavigateSubmit}>
        <label className="infotainment__label" htmlFor="infotainment-dest">
          Destination
        </label>
        <input
          id="infotainment-dest"
          className="infotainment__input"
          type="text"
          value={destination}
          autoComplete="street-address"
          placeholder="Home or address"
          onChange={(e) => setDestination(e.target.value)}
        />
      </form>

      <div className="infotainment__actions" role="group" aria-label="Open in maps">
        <a
          className="infotainment__btn"
          href={links.waze}
          target="_blank"
          rel="noreferrer"
        >
          Open in Waze
        </a>
        <a
          className="infotainment__btn"
          href={links.apple_maps}
          target="_blank"
          rel="noreferrer"
        >
          Open in Apple Maps
        </a>
      </div>

      <div className="infotainment__music">
        <div className="parked__history-head">
          <span>Spotify</span>
          <span className="parked__badge">Stub</span>
        </div>
        <p className="infotainment__hint">{SPOTIFY_SIRI_HINT}</p>
        <div className="infotainment__actions">
          <a
            className="infotainment__btn infotainment__btn--quiet"
            href={spotifyOpenUrl()}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => {
              // Prefer window.open from gesture when available
              e.preventDefault()
              openSpotifyFallback()
            }}
          >
            Open Spotify
          </a>
          <span className="infotainment__siri">or ask Siri</span>
        </div>
      </div>
    </section>
  )
}
