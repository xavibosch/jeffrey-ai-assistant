"""
Jeffrey — Speech to Text

Two-tier transcription:

  1. Deepgram (cloud)  — ~200-400ms. Free tier is generous; needs an API key.
  2. Whisper  (local)  — ~1-2s. Always available, works offline, no key.

Deepgram is tried first when a key exists. On quota exhaustion / auth failure /
network error we fall back to Whisper immediately AND remember the failure so we
stop hammering a dead endpoint (see _COOLDOWN).

Put your key in  ~/.jeffrey/deepgram_key.txt   or  env DEEPGRAM_API_KEY.
No key = Whisper only, everything keeps working.
"""
from faster_whisper import WhisperModel
from pathlib import Path
import os
import time

try:
    import requests
except Exception:
    requests = None

# ── Whisper (local fallback) ──────────────────────────────────────────────────
_model: WhisperModel | None = None
MODEL_SIZE = "small"  # small >> base for multilingual (Spanish + English)
DEFAULT_LANGUAGE = "es"  # pin Spanish: faster and more accurate than auto-detect
                         # on short commands. Pass language="en" to override.

# ── Deepgram (cloud primary) ──────────────────────────────────────────────────
DEEPGRAM_URL   = "https://api.deepgram.com/v1/listen"
# Tested on this account: nova-2 (any language) and nova-3 with language="es"
# both return an EMPTY transcript. Only nova-3 + language="multi" works, and it
# handles Spanish and English in the same utterance. `smart_format` adds ~0.6s
# for punctuation we don't need for commands, so it stays off.
DEEPGRAM_MODEL    = "nova-3"
DEEPGRAM_LANGUAGE = "multi"
DEEPGRAM_TIMEOUT  = 8          # seconds; Whisper takes over if slower

# When Deepgram fails for a quota/auth reason, skip it for this long (seconds)
# instead of paying the round-trip on every single utterance.
_COOLDOWN = 30 * 60
_deepgram_blocked_until = 0.0


def _get_deepgram_key() -> str | None:
    key = os.environ.get("DEEPGRAM_API_KEY", "").strip()
    if key:
        return key
    f = Path.home() / ".jeffrey" / "deepgram_key.txt"
    if f.exists():
        return f.read_text().strip() or None
    return None


def is_deepgram_configured() -> bool:
    return _get_deepgram_key() is not None


def _block_deepgram(reason: str) -> None:
    global _deepgram_blocked_until
    _deepgram_blocked_until = time.time() + _COOLDOWN
    mins = _COOLDOWN // 60
    print(f"[stt] Deepgram no disponible ({reason}) → Whisper local durante {mins} min")


def _transcribe_deepgram(audio_path: str, language: str) -> str | None:
    """Return transcript, or None if Deepgram can't serve this request."""
    if requests is None:
        return None
    if time.time() < _deepgram_blocked_until:
        return None            # still cooling down after a quota/auth failure
    key = _get_deepgram_key()
    if not key:
        return None

    try:
        with open(audio_path, "rb") as f:
            audio = f.read()
    except Exception:
        return None

    try:
        r = requests.post(
            DEEPGRAM_URL,
            params={
                "model": DEEPGRAM_MODEL,
                "language": DEEPGRAM_LANGUAGE,   # "multi" — see note above
                "punctuate": "true",
            },
            headers={"Authorization": f"Token {key}", "Content-Type": "audio/wav"},
            data=audio,
            timeout=DEEPGRAM_TIMEOUT,
        )
    except Exception as e:
        print(f"[stt] Deepgram error de red ({type(e).__name__}) → Whisper")
        return None

    # Quota exhausted / bad key / rate limited → stop trying for a while
    if r.status_code in (401, 402, 403, 429):
        _block_deepgram(f"HTTP {r.status_code}")
        return None
    if r.status_code != 200:
        print(f"[stt] Deepgram HTTP {r.status_code} → Whisper")
        return None

    try:
        alt = r.json()["results"]["channels"][0]["alternatives"][0]
        text = (alt.get("transcript") or "").strip()
    except Exception:
        return None

    if not text:
        # Empty transcript: either real silence, or a model/language combo this
        # account can't serve. Either way Whisper gets a turn.
        print("[stt] Deepgram devolvió vacío → Whisper")
        return None
    print(f"[stt] Deepgram: '{text}'")
    return text


# ── Whisper ───────────────────────────────────────────────────────────────────

def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        print("[stt] Loading Whisper model (first time may take a few seconds)...")
        _model = WhisperModel(
            MODEL_SIZE,
            device="cpu",          # use 'cuda' if you had a GPU
            compute_type="int8",   # fastest on CPU, good quality
        )
        print("[stt] Whisper ready.")
    return _model


def _transcribe_whisper(audio_path: str, language: str) -> str:
    model = _get_model()
    # Short commands don't need beam search: beam_size=1 is ~2x faster with
    # essentially the same accuracy here.
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=1,
        best_of=1,
        temperature=0.0,          # deterministic, no hallucination
        condition_on_previous_text=False,  # each utterance independent
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=200,
            speech_pad_ms=400,    # keep a bit more context around speech
        ),
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    conf = getattr(info, "language_probability", None)
    conf_s = f" ({conf:.0%})" if isinstance(conf, float) else ""
    print(f"[stt] Whisper {info.language}{conf_s}: '{text}'")
    return text


# ── Public API ────────────────────────────────────────────────────────────────

def transcribe(audio_path: str, language: str | None = None) -> str:
    """
    Transcribe a WAV file: Deepgram first (fast), Whisper as fallback (always).
    Never raises — returns "" if both fail.
    """
    lang = language or DEFAULT_LANGUAGE

    text = _transcribe_deepgram(audio_path, lang)
    if text:
        return text

    try:
        return _transcribe_whisper(audio_path, lang)
    except Exception as e:
        print(f"[stt] Whisper falló: {e}")
        return ""


def preload_model() -> None:
    """Warm the local model at startup so the fallback is instant when needed."""
    _get_model()


def backend_status() -> str:
    """Human-readable line for logs/UI."""
    if not is_deepgram_configured():
        return "STT: Whisper local (sin key de Deepgram)"
    if time.time() < _deepgram_blocked_until:
        left = int((_deepgram_blocked_until - time.time()) // 60)
        return f"STT: Whisper local (Deepgram en pausa {left} min)"
    return "STT: Deepgram → Whisper (fallback)"
