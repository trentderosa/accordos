/**
 * Spotify open / Siri fallback stub.
 * No client secrets. No OAuth tokens in the frontend.
 * Core AccordOS works without Spotify; PKCE path is documented only for now.
 */

export const SPOTIFY_OPEN_URL = 'https://open.spotify.com/' as const

export const SPOTIFY_SIRI_HINT =
  'Open Spotify or ask Siri — AccordOS does not control playback yet.' as const

export type SpotifyStubAction = {
  type: 'spotify_stub'
  requested: string
  executed: false
  open_url: string
  fallback: string
  oauth: 'pkce_documented_not_wired'
  client_secret_in_frontend: false
}

export function spotifyOpenUrl(): string {
  return SPOTIFY_OPEN_URL
}

export function spotifyStubAction(requested = 'open'): SpotifyStubAction {
  return {
    type: 'spotify_stub',
    requested,
    executed: false,
    open_url: SPOTIFY_OPEN_URL,
    fallback: SPOTIFY_SIRI_HINT,
    oauth: 'pkce_documented_not_wired',
    client_secret_in_frontend: false,
  }
}

/** Open Spotify in a new tab/window from a user gesture (parked shortcuts). */
export function openSpotifyFallback(): void {
  window.open(SPOTIFY_OPEN_URL, '_blank', 'noopener,noreferrer')
}
