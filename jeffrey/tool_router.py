"""
Jeffrey — Tool Router

Three improvements borrowed from agent-architecture practice:

1. PROGRESSIVE DISCLOSURE
   Sending all 86 tool schemas on every message costs ~5.5k tokens and confuses
   a small model. We score tools against the user's message and send only the
   most relevant ones (plus a small always-on core).

2. CONFIDENCE THRESHOLD
   If nothing scores above a floor, the message is ambiguous. Instead of forcing
   a tool call and guessing wrong, we let the model reply/ask.

3. TOKEN BUDGETING
   The payload is measured BEFORE the API call. If it exceeds the budget we drop
   the lowest-scoring tools until it fits, so we never send an oversized request.
"""
from __future__ import annotations
import json
import re

# ── Tuning knobs ──────────────────────────────────────────────────────────────
MAX_TOOLS         = 14      # how many tool schemas to send at most
MIN_SCORE         = 2.0     # below this, treat the request as ambiguous
TOKEN_BUDGET      = 2600    # approx tokens allowed for the tools payload
CHARS_PER_TOKEN   = 4       # rough estimate, good enough for budgeting

# Always available: cheap, common, and the model expects them to exist.
CORE_TOOLS = {
    "open_app", "get_time", "web_search", "read_screen",
    "send_notification", "run_shortcut",
}

# Words that carry no routing signal.
_STOP = {
    "el", "la", "los", "las", "un", "una", "de", "del", "al", "a", "en", "y", "o",
    "que", "qué", "es", "está", "estas", "por", "para", "con", "sin", "me", "mi",
    "te", "tu", "se", "lo", "le", "su", "hay", "ha", "he", "cuál", "cual", "cómo",
    "como", "cuánto", "cuanto", "cuánta", "cuanta", "dime", "puedes", "quiero",
    "the", "is", "a", "an", "of", "to", "in", "on", "for", "my", "me", "what",
    "how", "can", "you", "please", "jeffrey", "bosch",
}

# Extra hints per tool: words a user would say that don't appear in the schema.
_HINTS: dict[str, list[str]] = {
    "weather":            ["tiempo", "clima", "temperatura", "frio", "frío", "calor", "llueve", "lluvia", "sol", "grados"],
    "crypto_price":       ["bitcoin", "btc", "ethereum", "eth", "cripto", "moneda", "vale", "cuesta"],
    "stock_price":        ["accion", "acción", "acciones", "bolsa", "cotiza", "nasdaq", "apple", "tesla"],
    "currency_convert":   ["euros", "dolares", "dólares", "cambio", "divisa", "convertir"],
    "play_spotify":       ["musica", "música", "cancion", "canción", "spotify", "suena", "pon", "reproduce"],
    "current_track":      ["suena", "sonando", "cancion", "canción", "sona"],
    "battery_info":       ["bateria", "batería", "carga", "porcentaje", "pila"],
    "wifi_info":          ["wifi", "internet", "red", "conexion", "conexión"],
    "disk_space":         ["disco", "espacio", "almacenamiento", "lleno", "gb"],
    "mac_stats":          ["mac", "ordenador", "cpu", "ram", "memoria", "rendimiento", "va"],
    "get_time":           ["hora", "fecha", "dia", "día", "hoy", "ahora", "reloj"],
    "list_calendar_events": ["calendario", "agenda", "reunion", "reunión", "cita", "evento", "planes"],
    "create_calendar_event": ["calendario", "agenda", "apunta", "evento", "reunion", "reunión"],
    "list_reminders":     ["recordatorio", "recordatorios", "tareas", "pendiente", "lista"],
    "create_reminder":    ["recuerdame", "recuérdame", "recordatorio", "avisame", "avísame", "alarma"],
    "send_imessage":      ["mensaje", "escribe", "manda", "envia", "envía", "whatsapp", "imessage", "dile"],
    "compose_email":      ["email", "correo", "mail", "escribe"],
    "create_note":        ["nota", "apunta", "notas", "anota"],
    "generate_image":     ["imagen", "dibuja", "genera", "foto", "ilustra", "crea"],
    "generate_qr":        ["qr", "codigo", "código"],
    "translate":          ["traduce", "traducir", "traduccion", "traducción", "ingles", "inglés"],
    "calculate":          ["cuanto", "cuánto", "suma", "resta", "multiplica", "divide", "calcula", "por", "mas", "más"],
    "wikipedia_summary":  ["quien", "quién", "wikipedia", "historia", "informacion", "información", "sobre"],
    "define_word":        ["significa", "definicion", "definición", "define", "palabra"],
    "web_search":         ["busca", "buscar", "google", "internet", "encuentra", "noticias"],
    "read_screen":        ["pantalla", "ves", "leyendo", "aqui", "aquí", "esto", "mirando"],
    "screenshot_to_clipboard": ["captura", "screenshot", "pantallazo", "foto"],
    "roll_dice":          ["dado", "dados", "tira", "aleatorio", "numero", "número"],
    "flip_coin":          ["moneda", "cara", "cruz", "aire"],
    "tell_joke":          ["chiste", "gracioso", "risa", "broma"],
    "random_fact":        ["curioso", "dato", "curiosidad", "interesante"],
    "magic_8ball":        ["bola", "magica", "mágica", "deberia", "debería"],
    "open_app":           ["abre", "abrir", "lanza", "arranca", "pon"],
    "quit_app":           ["cierra", "cerrar", "quita", "sal"],
    "set_volume":         ["volumen", "sube", "baja", "alto", "bajo", "silencio"],
    "brightness_set":     ["brillo", "luz", "pantalla", "sube", "baja"],
    "lock_screen":        ["bloquea", "bloquear", "lock"],
    "sleep_mac":          ["duerme", "dormir", "apaga", "suspende"],
    "window_arrange":     ["ventana", "izquierda", "derecha", "coloca", "mueve", "pantalla"],
    "sports_scores":      ["partido", "futbol", "fútbol", "gano", "ganó", "quedo", "quedó", "barca", "barça", "madrid", "liga"],
    "news_briefing":      ["noticias", "actualidad", "mundo", "pasa", "titulares"],
    "hackernews_top":     ["hacker", "news", "tecnologia", "tecnología", "hn"],
    "list_files":         ["archivos", "carpeta", "directorio", "ficheros"],
    "search_files":       ["busca", "archivo", "fichero", "encuentra", "documento"],
    "read_file":          ["lee", "leer", "archivo", "abre", "contenido"],
    "run_shortcut":       ["atajo", "shortcut", "rutina", "automatizacion", "automatización"],
    "airpods_battery":    ["airpods", "auriculares", "cascos", "bateria", "batería"],
    "public_ip":          ["ip", "direccion", "dirección", "publica", "pública"],
    "generate_password":  ["contraseña", "password", "clave", "segura"],
    "find_my_iphone":     ["iphone", "movil", "móvil", "telefono", "teléfono", "buscar", "suene"],
    "clean_downloads":    ["descargas", "limpia", "borra", "downloads"],
    "find_large_files":   ["grandes", "ocupa", "espacio", "pesados", "libera"],
    "summarize_text":     ["resume", "resumen", "resumeme", "portapapeles"],
}


def _tokens(words: str) -> set[str]:
    """Normalise text into a set of comparable words (accents stripped)."""
    lowered = words.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ü", "u")):
        lowered = lowered.replace(a, b)
    return {w for w in re.findall(r"[a-z0-9ñ]+", lowered) if w not in _STOP and len(w) > 1}


def _tool_vocab(tool: dict) -> set[str]:
    """Words associated with a tool: its name, its description, and manual hints."""
    fn = tool.get("function", {})
    name = fn.get("name", "")
    vocab = _tokens(name.replace("_", " "))
    vocab |= _tokens(fn.get("description", ""))
    vocab |= _tokens(" ".join(_HINTS.get(name, [])))
    return vocab


# Patterns that pin a specific tool regardless of word overlap. These fix cases
# where several tools share vocabulary (e.g. "cuánto" → maths vs currency).
_PATTERNS: list[tuple[str, str, float]] = [
    # (regex, tool_name, bonus)
    (r"\d+\s*(por|x|\*|mas|más|\+|menos|-|entre|/|dividido)\s*\d+", "calculate", 8.0),
    (r"\b(cuanto|cuánto)\s+(es|son)\b.*\d",                          "calculate", 6.0),
    (r"\d+\s*(euros?|dolares?|dólares?|usd|eur|libras?)\b",          "currency_convert", 8.0),
    (r"\b(resume|resumeme|resúmeme|resumen)\b",                      "summarize_text", 8.0),
    (r"\b(copiado|portapapeles|clipboard)\b",                        "summarize_text", 4.0),
    (r"\b(apunta|anota|nota)\b",                                     "create_note", 5.0),
    (r"\b(recuerdame|recuérdame|recordatorio|avisame|avísame)\b",    "create_reminder", 6.0),
    (r"\bcaptura|pantallazo|screenshot\b",                           "screenshot_to_clipboard", 5.0),
    (r"\b(que|qué)\s+(hay|ves|pone|dice)\b.*\b(pantalla|aqui|aquí)\b", "read_screen", 6.0),
    # volume vs brightness share "sube/baja" — pin them by their own noun
    (r"\bvolumen\b|\bvolume\b|\bsonido\b",                           "set_volume", 8.0),
    (r"\bbrillo\b|\bbrightness\b",                                   "brightness_set", 8.0),
]

# Tools that must NOT win when a competing keyword is present.
_PENALTIES: list[tuple[str, str, float]] = [
    (r"\bvolumen\b|\bsonido\b", "brightness_set", -6.0),   # "sube el volumen" ≠ brillo
    (r"\bbrillo\b",             "set_volume",     -6.0),
]


def score_tools(message: str, tools: list[dict]) -> list[tuple[float, dict]]:
    """Score every tool against the message. Higher = more relevant."""
    words = _tokens(message)
    lowered = message.lower()

    # Pattern bonuses (strongest signal, resolves vocabulary collisions)
    pinned: dict[str, float] = {}
    for pattern, tool_name, bonus in _PATTERNS:
        if re.search(pattern, lowered):
            pinned[tool_name] = max(pinned.get(tool_name, 0.0), bonus)
    # Penalties push down tools that merely share vocabulary with the real target.
    for pattern, tool_name, penalty in _PENALTIES:
        if re.search(pattern, lowered):
            pinned[tool_name] = pinned.get(tool_name, 0.0) + penalty

    scored: list[tuple[float, dict]] = []
    for tool in tools:
        name = tool.get("function", {}).get("name", "")
        vocab = _tool_vocab(tool)
        overlap = words & vocab
        score = float(len(overlap))
        # Hint words are strong signals — weight them extra.
        hint_hits = words & _tokens(" ".join(_HINTS.get(name, [])))
        score += 1.5 * len(hint_hits)
        # Exact tool name mentioned (e.g. "spotify") is a very strong signal.
        if any(part in words for part in _tokens(name.replace("_", " "))):
            score += 1.0
        # Pattern pin wins over everything else.
        score += pinned.get(name, 0.0)
        scored.append((score, tool))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def _payload_tokens(tools: list[dict]) -> int:
    return len(json.dumps(tools)) // CHARS_PER_TOKEN


def select_tools(
    message: str,
    tools: list[dict],
    max_tools: int = MAX_TOOLS,
    budget: int = TOKEN_BUDGET,
) -> tuple[list[dict], float]:
    """
    Progressive disclosure + token budgeting.

    Returns (selected_tools, best_score).
    best_score lets the caller decide whether the request was clear enough
    to force a tool call (see CONFIDENCE THRESHOLD).
    """
    scored = score_tools(message, tools)
    best_score = scored[0][0] if scored else 0.0

    # Keep anything with a positive score, then top up with the core tools.
    chosen: list[dict] = [t for s, t in scored if s > 0][:max_tools]
    chosen_names = {t["function"]["name"] for t in chosen}
    for _s, t in scored:
        if len(chosen) >= max_tools:
            break
        name = t["function"]["name"]
        if name in CORE_TOOLS and name not in chosen_names:
            chosen.append(t)
            chosen_names.add(name)

    # Nothing matched at all → send the core set so the model still has options.
    if not chosen:
        chosen = [t for _s, t in scored if t["function"]["name"] in CORE_TOOLS][:max_tools]

    # TOKEN BUDGETING — trim from the bottom until the payload fits.
    while len(chosen) > 1 and _payload_tokens(chosen) > budget:
        chosen.pop()

    return chosen, best_score


def is_confident(best_score: float, threshold: float = MIN_SCORE) -> bool:
    """True when the message clearly maps to a tool (don't force one if not)."""
    return best_score >= threshold


def debug_selection(message: str, tools: list[dict]) -> str:
    """Human-readable explanation of a routing decision (for tuning)."""
    scored = score_tools(message, tools)[:6]
    chosen, best = select_tools(message, tools)
    lines = [f"message: {message!r}",
             f"best_score={best:.1f}  confident={is_confident(best)}  "
             f"tools_sent={len(chosen)}  tokens≈{_payload_tokens(chosen)}"]
    lines += [f"   {s:5.1f}  {t['function']['name']}" for s, t in scored]
    return "\n".join(lines)
