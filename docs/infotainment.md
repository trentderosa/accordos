# AccordOS — infotainment stubs (Phase 5 light)

Maps and Spotify are **external app deep links / open stubs**, not embedded live navigation or playback control. Core telemetry, trips, health, and voice intents work with these integrations disabled or offline.

## Maps (Waze + Apple Maps)

| Helper | Purpose |
|---|---|
| `encode_destination` | Percent-encode a human destination (`quote_plus` / `+` for spaces) |
| `waze_navigate_url` | `https://waze.com/ul?q=…&navigate=yes` |
| `apple_maps_directions_url` | `http://maps.apple.com/?daddr=…&dirflg=d` |
| `maps_deep_links` | Both URLs for the same destination |

**Implemented in:** `backend/infotainment/links.py` and `frontend/src/lib/mapsLinks.ts` (same encoding rules).

**UI:** Parked **Navigate & music** panel (`InfotainmentShortcuts`) with destination field + Open in Waze / Apple Maps. While driving, only a labeled note — interactive launchers stay parked-only (or clearly labeled). Voice `navigate_home` returns the same encoded stubs; it does **not** force-launch under iOS.

**Hard rules**

- Never scrape Waze, embed a full Waze/Apple Maps UI, or invent traffic / police / community reports.
- Never fabricate GPS “home” coordinates — destination text is owner-entered or the literal label `Home`.
- iOS may require a user gesture to leave the PWA; verify later under real gesture rules.

## Spotify

| Piece | Status |
|---|---|
| Open Spotify URL | Stub: `https://open.spotify.com/` |
| Siri fallback copy | Documented in UI + voice reply |
| OAuth PKCE + Web Playback / Control API | **Documented path only — not wired** |
| Client secret in frontend | **Forbidden** — never |

### OAuth PKCE path (future, owner approval)

When (and only when) the owner authorizes a Spotify Developer app and Premium/eligibility is confirmed:

1. Register a Spotify app; note **Client ID** only for the public PWA.
2. Use **Authorization Code with PKCE** (no client secret on device). Store refresh tokens only on the Pi backend behind local auth if needed — never commit secrets.
3. Scopes: start with minimal playback/control scopes; respect rate limits and active-device rules.
4. Fail open: if token missing, revoked, or offline → show open-Spotify / Siri fallback; cluster remains usable.
5. Do not promise music ducking with AccordOS TTS until the audio feasibility gate closes.

Until then: voice `pause_spotify` and the parked **Open Spotify** / “ask Siri” controls are stubs (`spotify_stub_action`).

## Tests

`pytest tests/test_infotainment_links.py` — encoding, deep-link shape, Spotify stub has no secrets, voice home links use the shared helper.

## Related

- Handoff §10 (navigation + Spotify constraints)
- [voice-intents.md](./voice-intents.md) — `navigate_home` / `pause_spotify`
- [api.md](./api.md) — voice stubs
- [security-and-power.md](./security-and-power.md) — secrets out of Git
