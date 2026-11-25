"""Voice intent routing (Phase 4) — deterministic, local, no shell."""

from .auth import require_voice_access
from .intents import SUPPORTED
from .service import VoiceService

__all__ = ["VoiceService", "SUPPORTED", "require_voice_access"]
