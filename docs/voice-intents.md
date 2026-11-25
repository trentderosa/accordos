# AccordOS voice intents (Phase 4 — routing only)

Deterministic **local** text → intent routing for car-focused commands. No wake-word training, no paid LLM, no shell execution, no audio retention by default.

## What this phase includes

| Piece | Status |
|---|---|
| Text → allowlisted intent router | Done |
| ~15s follow-up context (“that's all” ends) | Done |
| `POST /api/voice/command` (local **or** bearer token) | Done |
| Startup briefing (fuel + health; **no** previous-trip fuel cost) | Done |
| Parked **Voice lab** text demo UI | Done |
| Wake word (“Hey Accord”) / offline ASR / TTS | Not in this PR |
| Hardware mic / Pi audio path | Not started |

## Audio feasibility gate — **open**

iPhone PWA TTS, autoplay / user-gesture rules, screen lock, backgrounding, and Bluetooth mixing with Honda audio are **unproven**. AccordOS does not assume the Pi can force iOS speech playback. Until that gate closes, treat replies as text (Voice lab) and keep any spoken path as a future spike. No hardware changes in this phase.

## Supported intents

| Intent | Example text | Behavior |
|---|---|---|
| `fuel_level` | “How much fuel is left?” | Reads latest telemetry fuel %; honest if unavailable |
| `range_estimate` | “How far will that get me?” | Unavailable until calibrated — does **not** invent miles |
| `last_trip` | “How was my last trip?” | Summarizes latest finalized/recovered trip |
| `check_engine` | “Why is my check-engine light on?” | Explains active DTCs; codes ≠ diagnoses |
| `navigate_home` | “Navigate home” | Deep-link **stub** (Waze / Apple Maps URLs); does not force-launch |
| `pause_spotify` | “Pause Spotify” | Stub / fallback message (use Spotify app or Siri) |
| `end_session` | “That's all” | Clears follow-up context |

Unknown text → graceful failure. Arbitrary intents are rejected. **Never** maps speech to shell commands.

## Follow-ups

After a successful reply, the last intent stays active for **15 seconds** (configurable in `SessionContext`). Example:

1. “How much fuel is left?” → `fuel_level`
2. Within 15s: “How far will that get me?” / “and the range?” → `range_estimate`
3. “That's all” → session idle

## API

### `POST /api/voice/command`

Auth: **loopback local** without a token, **or** `Authorization: Bearer <ACCORDOS_VOICE_TOKEN>` for non-local clients.

```json
{ "text": "How much fuel is left?" }
```

or

```json
{ "intent": "fuel_level", "text": "optional" }
```

Response includes `ok`, `intent`, `reply`, `session`, `shell_executed: false`, and optional `action` stubs. Unknown → `ok: false`.

### `GET /api/voice/briefing`

Startup briefing lines from available fuel + health (+ one maintenance note when relevant). Always sets `includes_previous_trip_fuel_cost: false`.

### `GET /api/voice/session`

Current follow-up window + supported intent list + `audio_feasibility_gate: "open"`.

## Voice lab (UI)

In **parked** mode, the cluster shows a quiet **Voice lab** panel: type a command or tap a suggestion, see the reply and briefing. Keeps Tesla-like charcoal / white / soft blue language — no wake mic UI.

## Env

| Variable | Effect |
|---|---|
| `ACCORDOS_VOICE_TOKEN` | Optional bearer secret for non-local voice POSTs |

## Out of scope (still open)

- Custom “Hey Accord” wake model and USB mic on the Pi
- Offline speech recognition and local TTS pipeline
- Closing the iPhone PWA background-audio gate
- Real Spotify OAuth playback control and verified map launches under iOS gesture rules

## Try it

```bash
# backend running on :8000
curl -s http://127.0.0.1:8000/api/voice/briefing | python3 -m json.tool
curl -s -X POST http://127.0.0.1:8000/api/voice/command \
  -H 'Content-Type: application/json' \
  -d '{"text":"How much fuel is left?"}' | python3 -m json.tool
```

Or open the PWA → scenario **Parked** → **Voice lab**.
