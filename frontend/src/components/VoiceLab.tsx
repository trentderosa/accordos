import { useState } from 'react'
import type { FormEvent } from 'react'
import type { VoiceBriefing, VoiceCommandResult, VoiceSessionInfo } from '../types'

const SUGGESTIONS = [
  'How much fuel is left?',
  'How far will that get me?',
  'How was my last trip?',
  'Why is my check-engine light on?',
  "Navigate home",
  'Pause Spotify',
  "That's all",
]

interface Props {
  briefing: VoiceBriefing | null
  session: VoiceSessionInfo | null
  lastResult: VoiceCommandResult | null
  pending: boolean
  error: string | null
  onSend: (text: string) => Promise<unknown>
  onRefreshBriefing?: () => void
}

export function VoiceLab({
  briefing,
  session,
  lastResult,
  pending,
  error,
  onSend,
  onRefreshBriefing,
}: Props) {
  const [draft, setDraft] = useState('')
  const followupActive = Boolean(session?.session?.active)
  const remaining = session?.session?.followup_remaining_s

  async function submit(text: string) {
    const trimmed = text.trim()
    if (!trimmed || pending) return
    setDraft('')
    await onSend(trimmed)
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void submit(draft)
  }

  return (
    <section className="voice-lab" aria-label="Voice lab">
      <div className="voice-lab__head">
        <div>
          <h2 className="voice-lab__title">Voice lab</h2>
          <p className="voice-lab__lede">
            Type commands to exercise deterministic local intents — no wake-word training,
            no paid LLM. Audio TTS / background playback on the iPhone PWA is still unproven.
          </p>
        </div>
        <span className="parked__badge">
          {followupActive
            ? `Follow-up · ${remaining != null ? `${Math.ceil(remaining)}s` : 'open'}`
            : 'Idle'}
        </span>
      </div>

      {briefing ? (
        <div className="voice-lab__briefing" aria-label="Startup briefing">
          <div className="voice-lab__briefing-head">
            <span>Startup briefing</span>
            <button
              type="button"
              className="quiet-link"
              onClick={() => onRefreshBriefing?.()}
            >
              Refresh
            </button>
          </div>
          <p className="voice-lab__briefing-text">{briefing.spoken}</p>
          <p className="voice-lab__gate">
            Audio feasibility gate: open — PWA TTS / background audio unproven. No hardware.
          </p>
        </div>
      ) : null}

      <form className="voice-lab__form" onSubmit={onSubmit}>
        <label className="voice-lab__label" htmlFor="voice-lab-input">
          Command
        </label>
        <div className="voice-lab__row">
          <input
            id="voice-lab-input"
            className="voice-lab__input"
            type="text"
            value={draft}
            placeholder="How much fuel is left?"
            autoComplete="off"
            disabled={pending}
            onChange={(e) => setDraft(e.target.value)}
          />
          <button
            type="submit"
            className="voice-lab__send"
            disabled={pending || !draft.trim()}
          >
            {pending ? '…' : 'Send'}
          </button>
        </div>
      </form>

      <div className="voice-lab__suggestions" aria-label="Example commands">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            className="voice-chip"
            disabled={pending}
            onClick={() => void submit(s)}
          >
            {s}
          </button>
        ))}
      </div>

      {error ? <p className="voice-lab__error">{error}</p> : null}

      {lastResult ? (
        <div
          className={`voice-lab__reply ${lastResult.ok ? 'voice-lab__reply--ok' : 'voice-lab__reply--bad'}`}
          role="status"
          aria-live="polite"
        >
          <div className="voice-lab__reply-meta">
            <span>{lastResult.ok ? 'Reply' : 'Unknown'}</span>
            <span className="voice-lab__intent">
              {lastResult.intent ?? '—'}
              {lastResult.resolve ? ` · ${lastResult.resolve}` : ''}
            </span>
          </div>
          <p className="voice-lab__reply-text">{lastResult.reply}</p>
          {lastResult.action?.type === 'deep_link_stub' && lastResult.action.links ? (
            <div className="voice-lab__links">
              <a
                className="quiet-link"
                href={lastResult.action.links.waze}
                target="_blank"
                rel="noreferrer"
              >
                Waze stub
              </a>
              <span className="parked__export-sep" aria-hidden="true">
                ·
              </span>
              <a
                className="quiet-link"
                href={lastResult.action.links.apple_maps}
                target="_blank"
                rel="noreferrer"
              >
                Maps stub
              </a>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="parked__empty">No command yet — try a suggestion above.</p>
      )}
    </section>
  )
}
