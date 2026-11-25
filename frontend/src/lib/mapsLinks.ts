/**
 * Waze + Apple Maps deep-link helpers.
 * Encoded destinations only — no embedded maps, no fabricated traffic/police data.
 */

export function encodeDestination(destination: string): string {
  const cleaned = destination.trim()
  if (!cleaned) {
    throw new Error('destination must be a non-empty string')
  }
  // Spaces → + to match urllib.parse.quote_plus / map URL conventions
  return encodeURIComponent(cleaned).replace(/%20/g, '+')
}

export function wazeNavigateUrl(destination: string, navigate = true): string {
  const q = encodeDestination(destination)
  return `https://waze.com/ul?q=${q}&navigate=${navigate ? 'yes' : 'no'}`
}

export function appleMapsDirectionsUrl(
  destination: string,
  dirflg = 'd',
): string {
  const daddr = encodeDestination(destination)
  return `http://maps.apple.com/?daddr=${daddr}&dirflg=${encodeURIComponent(dirflg)}`
}

export function mapsDeepLinks(destination: string): {
  waze: string
  apple_maps: string
} {
  return {
    waze: wazeNavigateUrl(destination),
    apple_maps: appleMapsDirectionsUrl(destination),
  }
}
