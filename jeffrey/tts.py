import subprocess
import re

# Natural per-language voices (macOS `say`). Override by installing Premium voices
# in System Settings → Accessibility → Spoken Content → Manage Voices.
VOICE_ES = "Mónica"   # es_ES — natural Spanish (Spain)
VOICE_EN = "Daniel"   # en_GB — British, Jarvis vibe
RATE     = 175

_ES_CHARS = set("ñáéíóú¿¡ü")
_ES_WORDS = {
    "que", "el", "la", "los", "las", "de", "es", "está", "estoy", "no", "sí",
    "hola", "gracias", "señor", "bosch", "abre", "cierra", "pon", "qué", "cómo",
    "para", "con", "tu", "tus", "mi", "muy", "bien", "vale", "ahora", "tiempo",
    "hecho", "claro", "puedo", "tienes", "quieres", "voy", "hoy",
}


def _detect_lang(text: str) -> str:
    """Return 'es' or 'en' by simple heuristic."""
    low = text.lower()
    if any(c in _ES_CHARS for c in low):
        return "es"
    words = re.findall(r"[a-záéíóúñü]+", low)
    if not words:
        return "es"
    hits = sum(1 for w in words if w in _ES_WORDS)
    # Even a couple of Spanish function words → Spanish
    return "es" if hits >= 1 else "en"


def _voice_for(text: str) -> str:
    return VOICE_ES if _detect_lang(text) == "es" else VOICE_EN


def _clean(text: str) -> str:
    return (text
            .replace("**", "").replace("*", "")
            .replace("`", "").replace("#", "")
            .replace("\n\n", ". ").replace("\n", ", "))


def speak(text: str, voice: str = "", rate: int = RATE) -> None:
    """Speak text with macOS `say`, auto-picking a natural voice for the language."""
    clean = _clean(text)
    v = voice or _voice_for(clean)
    subprocess.run(["/usr/bin/say", "-v", v, "-r", str(rate), clean])


def speak_async(text: str, voice: str = "", rate: int = RATE) -> subprocess.Popen:
    """Non-blocking speak. Auto-picks the voice for the language."""
    clean = _clean(text)
    v = voice or _voice_for(clean)
    return subprocess.Popen(["/usr/bin/say", "-v", v, "-r", str(rate), clean])
