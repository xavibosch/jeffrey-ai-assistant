import requests
import json
import os
from pathlib import Path

OLLAMA_URL    = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:latest"

# ── NVIDIA NIM config ─────────────────────────────────────────────────────────
# build.nvidia.com → API Keys (free, 1000 credits signup)
# OpenAI-compatible endpoint — same key for all models
NVIDIA_URL     = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODELS  = [
    "meta/llama-3.1-8b-instruct",                # primary: ~1s. Forced tool_choice stops hallucination
    "meta/llama-3.3-70b-instruct",               # fallback 1: smarter
    "mistralai/mistral-large-2-instruct",        # fallback 2: great spanish
]
NVIDIA_FAST_MODEL = "meta/llama-3.1-8b-instruct"  # quick model for summarizing tool results

def _get_nvidia_key() -> str | None:
    key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if key:
        return key
    key_file = Path.home() / ".jeffrey" / "nvidia_key.txt"
    if key_file.exists():
        return key_file.read_text().strip() or None
    return None

# ── Gemini config ─────────────────────────────────────────────────────────────
# Google AI Studio: https://aistudio.google.com/apikey  (free, 1500 req/day)
GEMINI_MODEL  = "gemini-2.0-flash"
GEMINI_URL    = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

def _get_gemini_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    key_file = Path.home() / ".jeffrey" / "gemini_key.txt"
    if key_file.exists():
        return key_file.read_text().strip() or None
    return None

SYSTEM_PROMPT = """You are Jeffrey, a personal AI assistant running on a Mac. Sharp, concise, helpful — like Jarvis from Iron Man but real.

RULES:
- Answer in the SAME language the user speaks (Spanish → Spanish, English → English)
- Keep answers SHORT — spoken aloud via TTS. Max 2 sentences.
- No markdown, no bullet points, no emojis
- Be direct. No filler phrases.
- When tool results come back, summarize them naturally in 1-2 sentences.
- ALWAYS refer to the user as "Mr Bosch".

CONVERSATION:
- Greetings and small talk ("hola", "qué tal", "gracias", "quién eres") → reply warmly and naturally. NEVER refuse a greeting.
- You are friendly and personable, not a cold command parser.

TOOL USE:
- Call a tool when the user wants an action or real-time data (time, prices, weather, opening apps, files, etc.).
- For greetings/opinions/casual chat → just reply with text, no tool."""

# ── Tool definitions for Ollama function calling ───────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open or focus a macOS application",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {"type": "string", "description": "App name, e.g. Spotify, Safari, Notes"}
                },
                "required": ["app"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "quit_app",
            "description": "Quit/close a macOS application",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {"type": "string"}
                },
                "required": ["app"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a URL in a browser",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "browser": {"type": "string", "description": "Browser name, default Safari"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "switch_desktop",
            "description": "Switch to a macOS desktop/space by number (1-9)",
            "parameters": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer"}
                },
                "required": ["number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_spotify",
            "description": "Control Spotify: play a song, pause, next track, previous track, or resume",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Song or artist to search and play"},
                    "action": {"type": "string", "enum": ["play", "pause", "next", "previous", "resume"], "description": "Playback control"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for current information, news, prices, weather, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_screen",
            "description": "Read what is currently visible in an app or on screen. Use when user asks 'qué hay en X', 'qué ves en X', 'qué dice X', 'what is in X'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {"type": "string", "description": "App to read from: Safari, Notes, Terminal, Chrome, TextEdit. Leave empty to read current screen."},
                    "question": {"type": "string", "description": "What to look for"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current date and time",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command on the Mac",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string"}
                },
                "required": ["cmd"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_shortcut",
            "description": "Run a macOS Shortcut (from the Shortcuts app) by name. Use for complex automations the user has created: routines, focus modes, home automations, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Exact name of the Shortcut"},
                    "input": {"type": "string", "description": "Optional text to pass as input to the Shortcut"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_shortcuts",
            "description": "List all macOS Shortcuts available on this Mac",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text into the active app or a specific app",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "app": {"type": "string", "description": "Optional target app"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_clipboard",
            "description": "Read the current clipboard content",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_clipboard",
            "description": "Write text to the clipboard",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"]
            }
        }
    },
    # ── FILES ─────────────────────────────────────────
    {"type": "function", "function": {
        "name": "list_files",
        "description": "List files in a directory (e.g. ~/Desktop, ~/Documents). Use when asked to see contents of a folder.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read text from a specific file path on the Mac",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Write or append text to a file",
        "parameters": {"type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "append": {"type": "boolean"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "search_files",
        "description": "Search for files by name using Spotlight. Use when user asks to find a file.",
        "parameters": {"type": "object",
            "properties": {"query": {"type": "string"}, "where": {"type": "string"}},
            "required": ["query"]}}},
    # ── CALENDAR & REMINDERS ──────────────────────────
    {"type": "function", "function": {
        "name": "list_calendar_events",
        "description": "List upcoming calendar events. Use for 'qué tengo hoy', 'mi agenda', 'eventos de la semana'.",
        "parameters": {"type": "object", "properties": {"days": {"type": "integer", "description": "Number of days ahead (default 1)"}}}}},
    {"type": "function", "function": {
        "name": "create_calendar_event",
        "description": "Create a calendar event. Use for 'crea un evento', 'agéndame'.",
        "parameters": {"type": "object",
            "properties": {
                "title": {"type": "string"},
                "when": {"type": "string", "description": "Format: YYYY-MM-DD HH:MM"},
                "duration_minutes": {"type": "integer"},
                "calendar": {"type": "string"}},
            "required": ["title"]}}},
    {"type": "function", "function": {
        "name": "list_reminders",
        "description": "List pending reminders from Reminders.app",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "create_reminder",
        "description": "Create a reminder. Use for 'recuérdame', 'apunta que tengo que'.",
        "parameters": {"type": "object",
            "properties": {"title": {"type": "string"}, "when": {"type": "string", "description": "Format: YYYY-MM-DD HH:MM (optional)"}},
            "required": ["title"]}}},
    # ── MESSAGING ─────────────────────────────────────
    {"type": "function", "function": {
        "name": "send_imessage",
        "description": "Send an iMessage to a phone number or Apple ID",
        "parameters": {"type": "object",
            "properties": {"recipient": {"type": "string"}, "text": {"type": "string"}},
            "required": ["recipient", "text"]}}},
    {"type": "function", "function": {
        "name": "compose_email",
        "description": "Open Mail.app with a pre-filled draft email (does not send automatically)",
        "parameters": {"type": "object",
            "properties": {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}},
            "required": ["to"]}}},
    # ── NOTES ─────────────────────────────────────────
    {"type": "function", "function": {
        "name": "create_note",
        "description": "Create a new note in Notes.app. Use for 'crea una nota', 'apunta esto'.",
        "parameters": {"type": "object",
            "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
            "required": ["title"]}}},
    {"type": "function", "function": {
        "name": "append_to_note",
        "description": "Append text to an existing note (creates it if not found)",
        "parameters": {"type": "object",
            "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
            "required": ["title", "body"]}}},
    # ── SYSTEM INFO ───────────────────────────────────
    {"type": "function", "function": {
        "name": "battery_info",
        "description": "Get battery percentage and charging state. Use for 'cuánta batería tengo'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "wifi_info",
        "description": "Get current Wi-Fi network name. Use for 'a qué red wifi estoy conectado'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "disk_space",
        "description": "Show free disk space. Use for 'cuánto espacio libre tengo'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "public_ip",
        "description": "Get my current public IP address",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "running_apps_list",
        "description": "List apps that are currently open/running",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "current_track",
        "description": "Get the song currently playing in Spotify or Music",
        "parameters": {"type": "object", "properties": {}}}},
    # ── SYSTEM CONTROL ────────────────────────────────
    {"type": "function", "function": {
        "name": "lock_screen",
        "description": "Lock the Mac screen. Use for 'bloquea el mac'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "sleep_mac",
        "description": "Put the Mac to sleep. Use for 'duerme el mac', 'apaga el mac'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "send_notification",
        "description": "Show a macOS notification banner",
        "parameters": {"type": "object",
            "properties": {"title": {"type": "string"}, "message": {"type": "string"}},
            "required": ["title"]}}},
    {"type": "function", "function": {
        "name": "screenshot_to_clipboard",
        "description": "Take a screenshot and copy it to the clipboard",
        "parameters": {"type": "object", "properties": {}}}},
    # ── INFO / WEB ────────────────────────────────────
    {"type": "function", "function": {
        "name": "weather",
        "description": "Get current weather for a location. Use for 'qué tiempo hace', 'cómo está el tiempo en X'.",
        "parameters": {"type": "object",
            "properties": {"location": {"type": "string", "description": "City or place name (optional, uses IP if omitted)"}}}}},
    {"type": "function", "function": {
        "name": "translate",
        "description": "Translate text to another language. Use for 'cómo se dice X en Y', 'traduce esto'.",
        "parameters": {"type": "object",
            "properties": {"text": {"type": "string"}, "target": {"type": "string", "description": "Target language code: en, es, fr, de, it, ca, pt, etc."}},
            "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "define_word",
        "description": "Look up the definition of an English word",
        "parameters": {"type": "object", "properties": {"word": {"type": "string"}}, "required": ["word"]}}},
    {"type": "function", "function": {
        "name": "wikipedia_summary",
        "description": "Get a Wikipedia summary about a topic",
        "parameters": {"type": "object",
            "properties": {"topic": {"type": "string"}, "lang": {"type": "string", "description": "Language code, default 'es'"}},
            "required": ["topic"]}}},
    {"type": "function", "function": {
        "name": "calculate",
        "description": "Evaluate a math expression. Use for any math, e.g. '2*3+sqrt(16)'.",
        "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}},
    {"type": "function", "function": {
        "name": "currency_convert",
        "description": "Convert currency. Use for 'cuántos euros son 100 dolares'.",
        "parameters": {"type": "object",
            "properties": {"amount": {"type": "number"}, "src": {"type": "string"}, "dst": {"type": "string"}},
            "required": ["amount", "src", "dst"]}}},
    # ── LOCAL AI ──────────────────────────────────────
    {"type": "function", "function": {
        "name": "summarize_text",
        "description": "Summarize text using a local LLM. Source can be 'clipboard' (default) or text passed directly.",
        "parameters": {"type": "object",
            "properties": {"text": {"type": "string"}, "source": {"type": "string", "enum": ["clipboard", "param"]}}}}},
    # ── PERMISSIONS ───────────────────────────────────
    {"type": "function", "function": {
        "name": "grant_app_permissions",
        "description": "Trigger Automation permission dialogs for ALL installed apps at once. Use when user wants Jeffrey to have access to everything.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "open_system_settings",
        "description": "Open a System Settings privacy pane directly",
        "parameters": {"type": "object",
            "properties": {"pane": {"type": "string", "enum": ["automation", "accessibility", "screen", "microphone", "camera", "files", "input_monitoring"]}}}}},

    # ── MULTIMEDIA ────────────────────────────────────
    {"type": "function", "function": {"name": "record_screen",
        "description": "Record the screen for N seconds, save video to Desktop. Use for 'graba la pantalla'.",
        "parameters": {"type": "object", "properties": {"seconds": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "record_audio",
        "description": "Record microphone audio for N seconds to Desktop. Use for 'graba audio'.",
        "parameters": {"type": "object", "properties": {"seconds": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "take_photo",
        "description": "Take a silent webcam photo. Use for 'hazme una foto'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "ocr_screen_region",
        "description": "Capture a screen region and extract its text (OCR). Use for 'lee el texto de esta zona'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "color_pick",
        "description": "Pick a color from screen, return HEX. Use for 'dame el color de'.",
        "parameters": {"type": "object", "properties": {}}}},

    # ── REAL-TIME INFO ────────────────────────────────
    {"type": "function", "function": {"name": "crypto_price",
        "description": "Live cryptocurrency price. Use for 'precio del bitcoin', 'cuánto vale ethereum'.",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string", "description": "btc, eth, sol, etc."}}, "required": ["symbol"]}}},
    {"type": "function", "function": {"name": "stock_price",
        "description": "Live stock price. Use for 'precio de las acciones de Apple', symbol like AAPL, TSLA.",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}}},
    {"type": "function", "function": {"name": "hackernews_top",
        "description": "Top Hacker News stories now. Use for 'qué hay en hacker news'.",
        "parameters": {"type": "object", "properties": {"count": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "reddit_top",
        "description": "Top posts from a subreddit. Use for 'qué se dice en reddit de X'.",
        "parameters": {"type": "object", "properties": {"subreddit": {"type": "string"}, "count": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "news_briefing",
        "description": "World news headlines briefing. Use for 'dame las noticias', 'qué pasa en el mundo'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "github_repo_stats",
        "description": "GitHub repo stars/forks/issues. repo is 'owner/name'. Use for 'stats del repo X'.",
        "parameters": {"type": "object", "properties": {"repo": {"type": "string"}}, "required": ["repo"]}}},
    {"type": "function", "function": {"name": "movie_info",
        "description": "Movie/show info and rating. Use for 'háblame de la película X'.",
        "parameters": {"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}}},
    {"type": "function", "function": {"name": "sports_scores",
        "description": "Last match result for a team. Use for 'cómo quedó el Barça', 'resultado del Madrid'.",
        "parameters": {"type": "object", "properties": {"team": {"type": "string"}}, "required": ["team"]}}},
    {"type": "function", "function": {"name": "youtube_transcript",
        "description": "Get transcript of a YouTube video from URL. Use for 'resume este vídeo de youtube'.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},

    # ── CREATIVE AI ───────────────────────────────────
    {"type": "function", "function": {"name": "generate_image",
        "description": "Generate an image from a text description (free AI). Use for 'genera una imagen de', 'dibuja'.",
        "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}}},
    {"type": "function", "function": {"name": "generate_qr",
        "description": "Generate a QR code for text/URL. Use for 'crea un QR de'.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "remove_background",
        "description": "Remove background from an image file. Use for 'quita el fondo de esta imagen'.",
        "parameters": {"type": "object", "properties": {"image_path": {"type": "string"}}, "required": ["image_path"]}}},

    # ── DEV POWER ─────────────────────────────────────
    {"type": "function", "function": {"name": "git_status_all",
        "description": "Scan all git repos under a folder, list ones with uncommitted changes. Use for 'qué repos tengo sin commitear'.",
        "parameters": {"type": "object", "properties": {"base": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "run_test",
        "description": "Auto-detect and run tests (npm/pytest) in a project. Use for 'corre los tests'.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "json_format",
        "description": "Pretty-format JSON currently in clipboard. Use for 'formatea el json del portapapeles'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "regex_test",
        "description": "Test a regex pattern against text. Use for 'prueba este regex'.",
        "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "text": {"type": "string"}}, "required": ["pattern", "text"]}}},
    {"type": "function", "function": {"name": "generate_password",
        "description": "Generate a secure password to clipboard. Use for 'genérame una contraseña'.",
        "parameters": {"type": "object", "properties": {"length": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "hash_text",
        "description": "Hash text (md5/sha1/sha256/sha512). Use for 'dame el sha256 de'.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "algo": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "base64_tool",
        "description": "Base64 encode or decode text. Use for 'codifica en base64', 'decodifica'.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "mode": {"type": "string", "enum": ["encode", "decode"]}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "generate_uuid",
        "description": "Generate a UUID to clipboard. Use for 'dame un uuid'.",
        "parameters": {"type": "object", "properties": {}}}},

    # ── SYSTEM POWER ──────────────────────────────────
    {"type": "function", "function": {"name": "mac_stats",
        "description": "Show CPU load, memory pressure, uptime. Use for 'cómo va el Mac', 'estado del sistema'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "airpods_battery",
        "description": "Battery level of connected Bluetooth devices (AirPods). Use for 'batería de los airpods'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "window_arrange",
        "description": "Tile the front window: left/right/full/center. Use for 'pon la ventana a la izquierda'.",
        "parameters": {"type": "object", "properties": {"position": {"type": "string", "enum": ["left", "right", "full", "center"]}}, "required": ["position"]}}},
    {"type": "function", "function": {"name": "find_large_files",
        "description": "Find largest files on disk. Use for 'qué archivos ocupan más', 'libera espacio'.",
        "parameters": {"type": "object", "properties": {"base": {"type": "string"}, "min_gb": {"type": "number"}}}}},
    {"type": "function", "function": {"name": "clean_downloads",
        "description": "Move old Downloads files to Trash. Use for 'limpia las descargas'.",
        "parameters": {"type": "object", "properties": {"days": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "brightness_set",
        "description": "Set screen brightness 0-100. Use for 'baja el brillo', 'sube el brillo'.",
        "parameters": {"type": "object", "properties": {"level": {"type": "integer"}}, "required": ["level"]}}},
    {"type": "function", "function": {"name": "focus_mode",
        "description": "Toggle Do Not Disturb / focus mode. Use for 'activa no molestar', 'modo concentración'.",
        "parameters": {"type": "object", "properties": {"mode": {"type": "string", "enum": ["on", "off"]}}}}},
    {"type": "function", "function": {"name": "caffeinate_mac",
        "description": "Keep the Mac awake for N minutes. Use for 'no dejes que se duerma el Mac'.",
        "parameters": {"type": "object", "properties": {"minutes": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "bluetooth_toggle",
        "description": "Turn Bluetooth on/off/toggle. Use for 'apaga el bluetooth'.",
        "parameters": {"type": "object", "properties": {"state": {"type": "string", "enum": ["on", "off", "toggle"]}}}}},
    {"type": "function", "function": {"name": "find_my_iphone",
        "description": "Play a sound on the iPhone to find it. Use for 'busca mi iphone', 'haz sonar el móvil'.",
        "parameters": {"type": "object", "properties": {}}}},

    # ── FUN ───────────────────────────────────────────
    {"type": "function", "function": {"name": "roll_dice",
        "description": "Roll dice. Use for 'tira un dado', 'tira 2d20'.",
        "parameters": {"type": "object", "properties": {"sides": {"type": "integer"}, "count": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "flip_coin",
        "description": "Flip a coin, returns heads/tails. Use for 'cara o cruz', 'échame una moneda al aire', 'tira una moneda', 'lanza una moneda'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "magic_8ball",
        "description": "Magic 8-ball yes/no answer. Use for 'bola mágica', '¿debería...?'.",
        "parameters": {"type": "object", "properties": {"question": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "random_fact",
        "description": "A random interesting fact. Use for 'dime un dato curioso'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "tell_joke",
        "description": "Tell a joke. Use for 'cuéntame un chiste'.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "ascii_art",
        "description": "Render text as big ASCII art. Use for 'escribe X en ascii'.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
]


def _build_system_prompt() -> str:
    """Build system prompt with persona + live app list."""
    # Personal context
    persona_file = Path.home() / ".jeffrey" / "persona.md"
    try:
        persona_block = f"\n\n== PERSONAL CONTEXT ==\n{persona_file.read_text().strip()}"
    except Exception:
        persona_block = ""

    # App discovery
    try:
        from jeffrey.app_discovery import apps_context_string, get_running_apps
        installed = apps_context_string()
        running   = ", ".join(get_running_apps()) or "none"
        app_block = f"\n\n== INSTALLED APPS ==\n{installed}\n\n== CURRENTLY RUNNING ==\n{running}"
    except Exception:
        app_block = ""

    return SYSTEM_PROMPT + persona_block + app_block


# ── Shared OpenAI-compat caller ───────────────────────────────────────────────

def _parse_tool_call(choice: dict) -> dict | None:
    """Extract tool call from an OpenAI-format choice (used by both Gemini and Ollama OpenAI endpoint)."""
    msg = choice.get("message", {})
    tool_calls = msg.get("tool_calls") or []
    if tool_calls:
        tc   = tool_calls[0]
        name = tc["function"]["name"]
        args = tc["function"].get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        args["action"] = name
        return args
    return None


def _call_openai_compat(url: str, key: str, model: str, messages: list[dict],
                        tools: list | None = None, timeout: int = 30,
                        tool_choice: str | None = None) -> dict:
    """Generic OpenAI-compatible POST. Returns {"text", "tool_call", "error"}."""
    payload: dict = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        if resp.status_code == 429:
            return {"text": None, "tool_call": None, "error": "quota"}
        if resp.status_code == 402:
            return {"text": None, "tool_call": None, "error": "no_credits"}
        resp.raise_for_status()
        choice = resp.json()["choices"][0]
        tc = _parse_tool_call(choice)
        if tc:
            return {"text": None, "tool_call": tc, "error": None}
        text = (choice.get("message", {}).get("content") or "").strip()
        return {"text": text, "tool_call": None, "error": None}
    except requests.exceptions.Timeout:
        return {"text": None, "tool_call": None, "error": "timeout"}
    except Exception as e:
        return {"text": None, "tool_call": None, "error": str(e)}


def _chat_nvidia(messages: list[dict], force_tools: bool = False, use_tools: bool = True) -> dict:
    """
    Try NVIDIA NIM models in order.
    - force_tools=True  → tool_choice='required' (8B must call a tool, no hallucination)
    - use_tools=False   → send no tools at all (clean chat for greetings/small talk)
    """
    key = _get_nvidia_key()
    if not key:
        return {"text": None, "tool_call": None, "error": "no_key"}

    tools = TOOLS if use_tools else None
    tc    = "required" if (force_tools and use_tools) else None
    for model in NVIDIA_MODELS:
        result = _call_openai_compat(NVIDIA_URL, key, model, messages, tools=tools, tool_choice=tc)
        if result["error"] is None:
            tag = " [forced tool]" if tc else (" [chat]" if not use_tools else "")
            print(f"[jeffrey] Backend: NVIDIA {model.split('/')[-1]}{tag}")
            return result
        err = result["error"]
        if err in ("no_credits", "quota"):
            print(f"[jeffrey] NVIDIA {model.split('/')[-1]}: {err} → siguiente modelo")
            continue
        # Real error (timeout, network) — skip to next
        print(f"[jeffrey] NVIDIA {model.split('/')[-1]}: {err} → siguiente modelo")

    return {"text": None, "tool_call": None, "error": "all_nvidia_failed"}


def _chat_gemini(messages: list[dict]) -> dict:
    """Call Gemini 2.0 Flash. Returns {"text", "tool_call", "error"}."""
    key = _get_gemini_key()
    if not key:
        return {"text": None, "tool_call": None, "error": "no_key"}
    result = _call_openai_compat(GEMINI_URL, key, GEMINI_MODEL, messages, tools=TOOLS)
    if result["error"] is None:
        print("[jeffrey] Backend: Gemini 2.0 Flash")
    return result


# Keywords that indicate the user wants an action / real-time info (use tools)
_ACTION_KEYWORDS = {
    # app control
    "abre", "cierra", "pon", "open", "close", "quit", "lanza", "launch",
    # music
    "play", "pausa", "pause", "para", "reproduce", "canción", "track", "volumen", "volume",
    "spotify", "música", "music", "sube", "baja",
    # search / web
    "busca", "search", "encuentra", "find", "google", "duckduckgo",
    # time / date (MUST use tool for accurate info)
    "hora", "time", "fecha", "date", "día", "hoy", "ahora", "now",
    # weather / system info
    "clima", "tiempo", "weather", "temperatura", "temperature",
    "batería", "battery", "wifi", "internet", "red", "espacio", "disco",
    "ip", "ram", "cpu", "memoria",
    # messaging / email
    "manda", "send", "envía", "email", "mensaje", "message", "whatsapp", "imessage",
    # files / notes / calendar
    "crea", "escribe", "lee", "muestra", "nota", "note", "archivo", "file",
    "calendario", "calendar", "evento", "event", "recuerda", "reminder", "alarma",
    # screen / clipboard
    "pantalla", "screen", "screenshot", "captura", "clipboard", "portapapeles",
    # system control
    "bloquea", "lock", "apaga", "duerme", "sleep", "reinicia", "restart",
    "notificación", "notification",
    # ai / translate / calc
    "traduce", "translate", "calcula", "calculate", "convierte", "convert",
    "define", "wikipedia", "resumen", "summary", "moneda", "currency",
    # shortcuts / shell
    "ejecuta", "run", "shortcut", "comando", "command",
    # running apps / info
    "apps", "procesos", "processes",
}

# Pure conversation / greetings — these should NOT force a tool call.
_CHITCHAT = {
    "hola", "buenas", "hey", "ey", "qué", "que", "tal", "cómo", "como", "estás",
    "estas", "va", "gracias", "adiós", "adios", "chao", "hasta", "luego",
    "vale", "ok", "okay", "bien", "genial", "perfecto", "guay", "jeffrey",
    "quién", "quien", "eres", "llamas", "puedes", "hacer", "ayuda", "hello",
    "hi", "thanks", "bye", "sí", "si", "no", "claro",
}

def _is_chitchat(text: str) -> bool:
    """True if the message is a greeting / small talk (no tool needed)."""
    words = [w.strip("¿?¡!.,") for w in text.lower().split()]
    if not words:
        return True
    if len(words) > 6:               # long sentences are usually requests
        return False
    # Mostly chit-chat words → treat as conversation
    hits = sum(1 for w in words if w in _CHITCHAT)
    return hits >= max(1, len(words) - 1)


# Meta / explanatory questions ABOUT Jeffrey — answer with text, never a tool.
_META_PATTERNS = (
    "cual es tu", "cuál es tu", "como funciona", "cómo funciona",
    "como generas", "cómo generas", "como lo haces", "cómo lo haces",
    "como haces", "cómo haces", "como te", "cómo te", "que sistema", "qué sistema",
    "que modelo", "qué modelo", "que metodo", "qué método", "por que usas", "por qué usas",
    "explica", "explícame", "explicame", "que tecnologia", "qué tecnología",
    "como sabes", "cómo sabes", "de donde sacas", "de dónde sacas", "que api", "qué api",
    "puedes explicar", "como has", "cómo has", "con que", "con qué",
)

def _is_meta_question(text: str) -> bool:
    """True if asking HOW Jeffrey works (explain, not act)."""
    low = text.lower()
    return any(p in low for p in _META_PATTERNS)


def _looks_like_action(text: str) -> bool:
    """
    Should Jeffrey be forced to use a tool? Default YES (most inputs are commands /
    real-time questions). Greetings, small talk and meta questions skip tools.
    """
    if _is_chitchat(text) or _is_meta_question(text):
        return False
    return True


def _chat_ollama(messages: list[dict], model: str) -> dict:
    """
    Call local Ollama. Uses tools only when the message looks like an action request.
    Returns {"text": str | None, "tool_call": dict | None, "error": str | None}
    """
    # Extract last user message for heuristic
    last_user = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )
    use_tools = _looks_like_action(last_user)

    payload = {
        "model":    model,
        "messages": messages,
        "stream":   False,
    }
    if use_tools:
        payload["tools"] = TOOLS

    try:
        resp = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=60)
        resp.raise_for_status()
        msg = resp.json()["message"]

        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            tc   = tool_calls[0]
            name = tc["function"]["name"]
            args = tc["function"].get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)
            args["action"] = name
            return {"text": None, "tool_call": args, "error": None}

        return {"text": msg.get("content", "").strip(), "tool_call": None, "error": None}

    except requests.exceptions.ConnectionError:
        return {"text": None, "tool_call": None, "error": "ollama_offline"}
    except requests.exceptions.Timeout:
        return {"text": None, "tool_call": None, "error": "timeout"}
    except Exception as e:
        return {"text": None, "tool_call": None, "error": str(e)}


# ── Public API ────────────────────────────────────────────────────────────────

def chat(
    user_message: str,
    history: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
) -> dict:
    """
    Send a message. Tries Gemini first, falls back to Ollama.
    Returns {"text": str, "tool_call": dict | None}
    """
    system   = _build_system_prompt()
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # Greetings/small talk AND meta questions ("how do you generate images?")
    # → pure chat (no tools). Everything else → force a tool so the fast 8B model
    # can't invent times, prices, etc.
    no_tools    = _is_chitchat(user_message) or _is_meta_question(user_message)
    force_tools = not no_tools

    # 1️⃣ NVIDIA NIM (8B fast → 70B → mistral)
    nvidia = _chat_nvidia(messages, force_tools=force_tools, use_tools=not no_tools)
    if nvidia["error"] is None:
        return {"text": nvidia["text"], "tool_call": nvidia["tool_call"]}
    print(f"[jeffrey] NVIDIA failed ({nvidia['error']}) → Gemini")

    # 2️⃣ Gemini 2.0 Flash
    gemini = _chat_gemini(messages)
    if gemini["error"] is None:
        return {"text": gemini["text"], "tool_call": gemini["tool_call"]}
    print(f"[jeffrey] Gemini failed ({gemini['error']}) → Ollama")

    # 3️⃣ Ollama local (offline fallback)
    ollama = _chat_ollama(messages, model)
    if ollama["error"] is None:
        print(f"[jeffrey] Backend: Ollama ({model})")
        return {"text": ollama["text"], "tool_call": ollama["tool_call"]}

    if ollama["error"] == "ollama_offline":
        return {"text": "Sin conexión y Ollama offline. Ejecuta: ollama serve", "tool_call": None}
    return {"text": f"Error: {ollama['error']}", "tool_call": None}


def chat_with_tool_result(
    user_message: str,
    tool_name: str,
    tool_result: str,
    history: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Send tool result back to the model for a natural spoken response.
    Tries Gemini first, falls back to Ollama.
    """
    system   = _build_system_prompt()
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    messages.append({
        "role":    "assistant",
        "content": f"[Tool {tool_name} returned: {tool_result}]"
    })
    messages.append({
        "role":    "user",
        "content": "Summarize that result naturally in 1-2 sentences for Mr Bosch."
    })

    # Summarizing is simple → use a FAST small model to cut latency (~5s → ~1s).
    for fn, url, key, mdl in [
        ("NVIDIA", NVIDIA_URL,  _get_nvidia_key(),  NVIDIA_FAST_MODEL),
        ("Gemini", GEMINI_URL,  _get_gemini_key(),  GEMINI_MODEL),
    ]:
        if not key:
            continue
        r = _call_openai_compat(url, key, mdl, messages, tools=None, timeout=20)
        if r["error"] is None and r["text"]:
            return r["text"]

    # Ollama fallback
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except Exception:
        return tool_result  # last resort: raw result


def is_ollama_running() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def is_nvidia_configured() -> bool:
    return _get_nvidia_key() is not None

def is_gemini_configured() -> bool:
    return _get_gemini_key() is not None

def is_any_cloud_configured() -> bool:
    return is_nvidia_configured() or is_gemini_configured()


def list_models() -> list[str]:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []
