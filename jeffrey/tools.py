"""
Jeffrey Tool Executor
Each function maps to an action the LLM can trigger.
All return a dict: {"ok": bool, "result": str}
"""
import subprocess
import time


# ── HELPERS ────────────────────────────────────────────────

def _osascript(script: str) -> tuple[bool, str]:
    """Run an AppleScript string. Returns (ok, output)."""
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0, (r.stdout.strip() or r.stderr.strip())
    except Exception as e:
        return False, str(e)


def _shell(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip() or r.stderr.strip()
    except Exception as e:
        return False, str(e)


# ── TOOLS ──────────────────────────────────────────────────

def open_app(app: str, **_) -> dict:
    """Open or focus any macOS application."""
    ok, out = _osascript(f'tell application "{app}" to activate')
    if ok:
        return {"ok": True, "result": f"{app} abierto."}
    # Fallback: try NSWorkspace via open command
    ok2, out2 = _shell(["open", "-a", app])
    if ok2:
        return {"ok": True, "result": f"{app} abierto."}
    return {"ok": False, "result": f"No pude abrir {app}: {out}"}


def quit_app(app: str, **_) -> dict:
    """Quit an application."""
    ok, out = _osascript(f'tell application "{app}" to quit')
    return {"ok": ok, "result": f"{app} cerrado." if ok else f"Error: {out}"}


def open_url(url: str, browser: str = "Safari", **_) -> dict:
    """Open a URL in the default browser or a specific one."""
    if not url.startswith("http"):
        url = "https://" + url
    ok, out = _osascript(f'tell application "{browser}" to open location "{url}"')
    if not ok:
        ok, out = _shell(["open", url])
    return {"ok": ok, "result": f"Abriendo {url}" if ok else f"Error: {out}"}


def switch_desktop(number: int, **_) -> dict:
    """Switch to a specific macOS desktop (1-9) using Quartz CGEvent."""
    # Key codes: 1=18, 2=19, 3=20, 4=21, 5=23, 6=22, 7=26, 8=28, 9=25
    key_map = {1: 18, 2: 19, 3: 20, 4: 21, 5: 23, 6: 22, 7: 26, 8: 28, 9: 25}
    kc = key_map.get(int(number))
    if not kc:
        return {"ok": False, "result": f"Desktop {number} no válido (1-9)."}
    try:
        import Quartz
        src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
        keydown = Quartz.CGEventCreateKeyboardEvent(src, kc, True)
        keyup   = Quartz.CGEventCreateKeyboardEvent(src, kc, False)
        ctrl    = Quartz.kCGEventFlagMaskControl
        Quartz.CGEventSetFlags(keydown, ctrl)
        Quartz.CGEventSetFlags(keyup,   ctrl)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, keydown)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, keyup)
        return {"ok": True, "result": f"Cambiado al desktop {number}."}
    except Exception as e:
        return {"ok": False, "result": f"Error switch_desktop: {e}. Concede acceso en Ajustes → Privacidad → Accesibilidad → Terminal."}


def play_spotify(query: str = "", uri: str = "", action: str = "play", **_) -> dict:
    """Control Spotify: play a song/artist, pause, next, previous."""
    if action == "pause":
        ok, _ = _osascript('tell application "Spotify" to pause')
        return {"ok": ok, "result": "Spotify pausado."}
    if action == "next":
        ok, _ = _osascript('tell application "Spotify" to next track')
        return {"ok": ok, "result": "Siguiente canción."}
    if action == "previous":
        ok, _ = _osascript('tell application "Spotify" to previous track')
        return {"ok": ok, "result": "Canción anterior."}
    if action == "resume":
        ok, _ = _osascript('tell application "Spotify" to play')
        return {"ok": ok, "result": "Spotify reanudado."}

    # Play a specific song/artist by searching
    if query:
        # Open Spotify and search
        search_url = f"spotify:search:{query.replace(' ', '%20')}"
        ok, _ = _osascript(f'tell application "Spotify" to activate')
        time.sleep(0.5)
        # Use Cmd+L to open search
        _osascript('tell application "System Events" to keystroke "l" using {command down}')
        time.sleep(0.3)
        _osascript(f'tell application "System Events" to keystroke "{query}"')
        time.sleep(0.3)
        _osascript('tell application "System Events" to key code 36')  # Enter
        return {"ok": True, "result": f"Buscando '{query}' en Spotify."}

    if uri:
        ok, _ = _osascript(f'tell application "Spotify" to play track "{uri}"')
        return {"ok": ok, "result": "Reproduciendo en Spotify."}

    ok, _ = _osascript('tell application "Spotify" to play')
    return {"ok": ok, "result": "Spotify reproduciendo."}


def set_volume(level: int, **_) -> dict:
    """Volume control is disabled for safety."""
    return {"ok": False, "result": "El control de volumen está desactivado."}


def type_text(text: str, app: str = "", **_) -> dict:
    """Type text into the frontmost app (or a specific one)."""
    if app:
        _osascript(f'tell application "{app}" to activate')
        time.sleep(0.3)
    # Escape special chars for AppleScript
    safe = text.replace('"', '\\"').replace("\\", "\\\\")
    ok, out = _osascript(
        f'tell application "System Events" to keystroke "{safe}"'
    )
    return {"ok": ok, "result": f"Texto escrito." if ok else f"Error: {out}"}


def run_shortcut(name: str, input: str = "", **_) -> dict:
    """Run a macOS Shortcut by name, optionally passing text input."""
    cmd = ["shortcuts", "run", name]
    if input:
        # pass text via stdin
        try:
            r = subprocess.run(
                cmd, input=input, capture_output=True, text=True, timeout=30
            )
            out = (r.stdout + r.stderr).strip()[:300]
            return {"ok": r.returncode == 0, "result": out or f"Shortcut '{name}' ejecutado."}
        except Exception as e:
            return {"ok": False, "result": str(e)}
    ok, out = _shell(cmd, timeout=30)
    return {"ok": ok, "result": out or f"Shortcut '{name}' ejecutado."}


def list_shortcuts(**_) -> dict:
    """List all available macOS Shortcuts by name."""
    ok, out = _shell(["shortcuts", "list"], timeout=10)
    if not ok:
        return {"ok": False, "result": f"No pude listar shortcuts: {out}"}
    names = [line.strip() for line in out.splitlines() if line.strip()]
    return {"ok": True, "result": "Shortcuts disponibles:\n" + "\n".join(f"• {n}" for n in names)}


def run_shell(cmd: str, **_) -> dict:
    """Run a safe shell command and return output."""
    # Basic safety: block destructive commands
    BLOCKED = ["rm -rf", "sudo", "mkfs", "dd if=", "> /dev/", "chmod 777"]
    for b in BLOCKED:
        if b in cmd.lower():
            return {"ok": False, "result": f"Comando bloqueado por seguridad: {b}"}
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=15
        )
        out = (r.stdout + r.stderr).strip()[:500]
        return {"ok": r.returncode == 0, "result": out or "Ejecutado sin output."}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def get_current_time(**_) -> dict:
    """Get current date and time."""
    from datetime import datetime
    now = datetime.now()
    return {"ok": True, "result": now.strftime("%H:%M del %A %d de %B de %Y")}


def read_clipboard(**_) -> dict:
    """Read current clipboard content."""
    ok, out = _shell(["pbpaste"])
    return {"ok": ok, "result": out[:500] if out else "Portapapeles vacío."}


def write_clipboard(text: str, **_) -> dict:
    """Write text to clipboard."""
    try:
        subprocess.run(["pbcopy"], input=text.encode(), check=True)
        return {"ok": True, "result": "Copiado al portapapeles."}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def web_search(query: str, **_) -> dict:
    """Search the web using DuckDuckGo and return top results."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=4):
                title = r.get("title", "")
                body  = r.get("body", "")[:200]
                href  = r.get("href", "")
                results.append(f"• {title}: {body} ({href})")
        if not results:
            return {"ok": False, "result": "No encontré resultados para esa búsqueda."}
        return {"ok": True, "result": "\n".join(results)}
    except Exception as e:
        return {"ok": False, "result": f"Error buscando: {e}"}


def read_screen(question: str = "What is on screen?", app: str = "", **_) -> dict:
    """Read content from an app using Accessibility/osascript — reliable, no vision model needed."""

    target = app.strip() if app else _get_frontmost_app()

    # Try app-specific readers first (accurate, no hallucination)
    readers = {
        "safari":   _read_safari,
        "chrome":   _read_chrome,
        "notes":    _read_notes,
        "terminal": _read_terminal,
        "iterm2":   _read_terminal,
        "textedit": _read_textedit,
    }
    key = target.lower().replace(" ", "")
    for pattern, fn in readers.items():
        if pattern in key:
            return fn(question)

    # Generic fallback: get window title + selected text
    return _read_generic(target, question)


def _get_frontmost_app() -> str:
    ok, out = _osascript('tell application "System Events" to get name of first application process whose frontmost is true')
    return out.strip() if ok else "unknown"


def _read_safari(question: str) -> dict:
    script = '''
    tell application "Safari"
        set u to URL of current tab of front window
        set t to name of current tab of front window
        set sel to do JavaScript "window.getSelection().toString()" in current tab of front window
    end tell
    return t & " | " & u & " | selected: " & sel
    '''
    ok, out = _osascript(script)
    if ok and out.strip():
        return {"ok": True, "result": f"Safari: {out.strip()}"}
    return {"ok": False, "result": "No pude leer Safari. ¿Está abierto con una página?"}


def _read_chrome(question: str) -> dict:
    script = '''
    tell application "Google Chrome"
        set u to URL of active tab of front window
        set t to title of active tab of front window
    end tell
    return t & " | " & u
    '''
    ok, out = _osascript(script)
    if ok and out.strip():
        return {"ok": True, "result": f"Chrome: {out.strip()}"}
    return {"ok": False, "result": "No pude leer Chrome."}


def _read_notes(question: str) -> dict:
    script = '''
    tell application "Notes"
        set n to the first note
        set t to the name of n
        set b to the plaintext of n
    end tell
    return "Note: " & t & " — " & (text 1 thru (min 800 of (length of b)) of b)
    '''
    ok, out = _osascript(script)
    if ok and out.strip():
        return {"ok": True, "result": out.strip()}
    return {"ok": False, "result": "No pude leer Notes. ¿Hay una nota abierta?"}


def _read_terminal(question: str) -> dict:
    # Try Terminal.app first
    script = '''
    tell application "Terminal"
        set c to contents of selected tab of front window
    end tell
    return text -800 thru -1 of c
    '''
    ok, out = _osascript(script)
    if ok and out.strip():
        return {"ok": True, "result": f"Terminal: {out.strip()}"}
    return {"ok": False, "result": "No pude leer el terminal."}


def _read_textedit(question: str) -> dict:
    script = '''
    tell application "TextEdit"
        set c to text of front document
    end tell
    return text 1 thru (min 800 of (length of c)) of c
    '''
    ok, out = _osascript(script)
    if ok and out.strip():
        return {"ok": True, "result": out.strip()}
    return {"ok": False, "result": "No pude leer TextEdit."}


def _read_generic(app: str, question: str) -> dict:
    """Fallback: get window title and any selected text."""
    script = f'''
    tell application "System Events"
        tell process "{app}"
            set t to title of front window
        end tell
    end tell
    return t
    '''
    ok, out = _osascript(script)
    title = out.strip() if ok else ""

    # Also try to get selected text via clipboard trick
    _osascript('tell application "System Events" to keystroke "c" using {command down}')
    time.sleep(0.2)
    clip_ok, clip = _shell(["pbpaste"])
    selected = clip.strip()[:400] if clip_ok and clip.strip() else ""

    if title or selected:
        parts = []
        if title:
            parts.append(f"Ventana: {title}")
        if selected:
            parts.append(f"Texto seleccionado: {selected}")
        return {"ok": True, "result": " | ".join(parts)}

    return {"ok": False, "result": f"No pude leer contenido de {app}."}


# ── FILE SYSTEM ────────────────────────────────────────────

def list_files(path: str = "~", **_) -> dict:
    """List files in a directory."""
    import os
    p = os.path.expanduser(path)
    if not os.path.isdir(p):
        return {"ok": False, "result": f"No existe: {path}"}
    try:
        items = sorted(os.listdir(p))[:50]
        return {"ok": True, "result": f"{p}: " + ", ".join(items)}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def read_file(path: str, **_) -> dict:
    """Read text content of a file (max 4 KB)."""
    import os
    p = os.path.expanduser(path)
    if not os.path.isfile(p):
        return {"ok": False, "result": f"No existe: {path}"}
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(4000)
        return {"ok": True, "result": content}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def write_file(path: str, content: str, append: bool = False, **_) -> dict:
    """Write or append text to a file."""
    import os
    p = os.path.expanduser(path)
    try:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        mode = "a" if append else "w"
        with open(p, mode, encoding="utf-8") as f:
            f.write(content)
        return {"ok": True, "result": f"Escrito en {p}."}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def search_files(query: str, where: str = "~", **_) -> dict:
    """Search files by name using Spotlight (mdfind)."""
    import os
    base = os.path.expanduser(where)
    ok, out = _shell(["mdfind", "-onlyin", base, query], timeout=15)
    if not ok or not out:
        return {"ok": False, "result": f"Sin resultados para '{query}'."}
    lines = out.split("\n")[:15]
    return {"ok": True, "result": "\n".join(lines)}


# ── CALENDAR & REMINDERS ───────────────────────────────────

def list_calendar_events(days: int = 1, **_) -> dict:
    """List calendar events for the next N days."""
    script = f'''
    set today to current date
    set future to today + {days} * days
    set output to ""
    tell application "Calendar"
        repeat with cal in calendars
            try
                set evs to (every event of cal whose start date >= today and start date <= future)
                repeat with e in evs
                    set output to output & (summary of e) & " — " & (start date of e as string) & linefeed
                end repeat
            end try
        end repeat
    end tell
    return output
    '''
    ok, out = _osascript(script)
    if ok and out.strip():
        return {"ok": True, "result": out.strip()}
    return {"ok": True, "result": "No hay eventos próximos."}


def create_calendar_event(title: str, when: str = "", duration_minutes: int = 60, calendar: str = "", **_) -> dict:
    """Create a calendar event. when example: '2025-12-31 18:00'."""
    from datetime import datetime, timedelta
    try:
        if when:
            dt = datetime.strptime(when, "%Y-%m-%d %H:%M")
        else:
            dt = datetime.now() + timedelta(hours=1)
    except ValueError:
        return {"ok": False, "result": "Formato fecha inválido. Usa YYYY-MM-DD HH:MM"}

    end = dt + timedelta(minutes=duration_minutes)
    fmt_start = dt.strftime("%m/%d/%Y %H:%M")
    fmt_end   = end.strftime("%m/%d/%Y %H:%M")

    cal_clause = f'tell calendar "{calendar}"' if calendar else 'tell calendar 1'

    script = f'''
    tell application "Calendar"
        {cal_clause}
            make new event with properties {{summary:"{title}", start date:date "{fmt_start}", end date:date "{fmt_end}"}}
        end tell
    end tell
    return "ok"
    '''
    ok, out = _osascript(script)
    if ok:
        return {"ok": True, "result": f"Evento '{title}' creado para {dt.strftime('%d/%m %H:%M')}."}
    return {"ok": False, "result": f"Error creando evento: {out}"}


def list_reminders(**_) -> dict:
    """List pending reminders."""
    script = '''
    set output to ""
    tell application "Reminders"
        set pending to (every reminder of default list whose completed is false)
        repeat with r in pending
            set output to output & (name of r) & linefeed
        end repeat
    end tell
    return output
    '''
    ok, out = _osascript(script)
    if ok and out.strip():
        return {"ok": True, "result": out.strip()}
    return {"ok": True, "result": "No hay recordatorios pendientes."}


def create_reminder(title: str, when: str = "", **_) -> dict:
    """Create a reminder. when example: '2025-12-31 18:00' (optional)."""
    if when:
        try:
            from datetime import datetime
            dt = datetime.strptime(when, "%Y-%m-%d %H:%M")
            fmt = dt.strftime("%m/%d/%Y %H:%M")
            script = f'''
            tell application "Reminders"
                tell default list
                    make new reminder with properties {{name:"{title}", remind me date:date "{fmt}"}}
                end tell
            end tell
            return "ok"
            '''
        except ValueError:
            return {"ok": False, "result": "Formato fecha inválido. Usa YYYY-MM-DD HH:MM"}
    else:
        script = f'''
        tell application "Reminders"
            tell default list
                make new reminder with properties {{name:"{title}"}}
            end tell
        end tell
        return "ok"
        '''
    ok, out = _osascript(script)
    return {"ok": ok, "result": f"Recordatorio '{title}' creado." if ok else out}


# ── MESSAGING ──────────────────────────────────────────────

def send_imessage(recipient: str, text: str, **_) -> dict:
    """Send an iMessage. recipient = phone or email."""
    safe = text.replace('"', '\\"')
    script = f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy "{recipient}" of targetService
        send "{safe}" to targetBuddy
    end tell
    return "ok"
    '''
    ok, out = _osascript(script)
    return {"ok": ok, "result": f"Mensaje enviado a {recipient}." if ok else f"Error: {out}"}


def compose_email(to: str, subject: str = "", body: str = "", **_) -> dict:
    """Open Mail.app with a new email pre-filled (does not send)."""
    safe_subj = subject.replace('"', '\\"')
    safe_body = body.replace('"', '\\"')
    script = f'''
    tell application "Mail"
        set newMsg to make new outgoing message with properties {{subject:"{safe_subj}", content:"{safe_body}", visible:true}}
        tell newMsg
            make new to recipient at end of to recipients with properties {{address:"{to}"}}
        end tell
        activate
    end tell
    return "ok"
    '''
    ok, out = _osascript(script)
    return {"ok": ok, "result": f"Email para {to} preparado en Mail.app (revisa y envía tú)." if ok else out}


# ── NOTES ──────────────────────────────────────────────────

def create_note(title: str, body: str = "", **_) -> dict:
    """Create a new note in Notes.app."""
    safe_t = title.replace('"', '\\"')
    safe_b = body.replace('"', '\\"').replace("\n", "<br>")
    script = f'''
    tell application "Notes"
        tell account 1
            make new note with properties {{name:"{safe_t}", body:"{safe_b}"}}
        end tell
    end tell
    return "ok"
    '''
    ok, out = _osascript(script)
    return {"ok": ok, "result": f"Nota '{title}' creada." if ok else out}


def append_to_note(title: str, body: str, **_) -> dict:
    """Append text to an existing note (or create if not found)."""
    safe_t = title.replace('"', '\\"')
    safe_b = body.replace('"', '\\"').replace("\n", "<br>")
    script = f'''
    tell application "Notes"
        try
            set n to first note whose name is "{safe_t}"
            set body of n to (body of n) & "<br>" & "{safe_b}"
        on error
            tell account 1
                make new note with properties {{name:"{safe_t}", body:"{safe_b}"}}
            end tell
        end try
    end tell
    return "ok"
    '''
    ok, out = _osascript(script)
    return {"ok": ok, "result": f"Añadido a nota '{title}'." if ok else out}


# ── SYSTEM INFO ────────────────────────────────────────────

def battery_info(**_) -> dict:
    """Get battery percentage and status."""
    ok, out = _shell(["pmset", "-g", "batt"])
    if not ok:
        return {"ok": False, "result": "No pude leer la batería."}
    # Extract percentage and charging state
    import re
    m = re.search(r"(\d+%);\s*(\w+)", out)
    if m:
        return {"ok": True, "result": f"Batería: {m.group(1)} ({m.group(2)})"}
    return {"ok": True, "result": out[:200]}


def wifi_info(**_) -> dict:
    """Get current Wi-Fi network name (SSID)."""
    import re
    # 1) ipconfig getsummary — works on modern macOS where networksetup is broken
    for iface in ("en0", "en1"):
        ok, out = _shell(["ipconfig", "getsummary", iface], timeout=5)
        if ok and out:
            m = re.search(r"\bSSID\s*:\s*(.+)", out)
            if m and m.group(1).strip() not in ("", "<redacted>"):
                return {"ok": True, "result": f"Wi-Fi: {m.group(1).strip()}"}
            # SSID redacted (no Location permission) but we ARE connected
            if "SSID" in out:
                return {"ok": True, "result": "Conectado a Wi-Fi (nombre oculto: falta permiso de Ubicación)."}
    # 2) networksetup fallback
    for iface in ("en0", "en1"):
        ok, out = _shell(["networksetup", "-getairportnetwork", iface])
        if ok and "Current Wi-Fi Network:" in out:
            return {"ok": True, "result": f"Wi-Fi: {out.split(':', 1)[1].strip()}"}
    return {"ok": False, "result": "Sin conexión Wi-Fi."}


def disk_space(**_) -> dict:
    """Show free disk space."""
    ok, out = _shell(["df", "-h", "/"])
    if not ok:
        return {"ok": False, "result": out}
    lines = out.split("\n")
    if len(lines) >= 2:
        parts = lines[1].split()
        if len(parts) >= 4:
            return {"ok": True, "result": f"Disco: {parts[3]} libres de {parts[1]} ({parts[4]} usado)"}
    return {"ok": True, "result": out}


def public_ip(**_) -> dict:
    """Get current public IP."""
    import requests
    try:
        r = requests.get("https://api.ipify.org", timeout=5)
        return {"ok": True, "result": f"IP pública: {r.text.strip()}"}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def running_apps_list(**_) -> dict:
    """List currently running visible apps."""
    try:
        from jeffrey.app_discovery import get_running_apps
        apps = get_running_apps()
        return {"ok": True, "result": ", ".join(apps) if apps else "Ninguna app visible."}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def current_track(**_) -> dict:
    """Get current track from Spotify or Music."""
    # Spotify first
    script_sp = '''
    tell application "Spotify"
        if it is running then
            return (name of current track) & " — " & (artist of current track)
        end if
    end tell
    return ""
    '''
    ok, out = _osascript(script_sp)
    if ok and out.strip():
        return {"ok": True, "result": f"Spotify: {out.strip()}"}

    # Music app
    script_m = '''
    tell application "Music"
        if it is running then
            return (name of current track) & " — " & (artist of current track)
        end if
    end tell
    return ""
    '''
    ok, out = _osascript(script_m)
    if ok and out.strip():
        return {"ok": True, "result": f"Music: {out.strip()}"}

    return {"ok": True, "result": "Nada sonando."}


# ── SYSTEM CONTROL ─────────────────────────────────────────

def lock_screen(**_) -> dict:
    """Lock the Mac screen."""
    ok, out = _shell([
        "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
        "-suspend"
    ])
    if ok:
        return {"ok": True, "result": "Mac bloqueado."}
    # Fallback
    ok, out = _osascript('tell application "System Events" to keystroke "q" using {control down, command down}')
    return {"ok": ok, "result": "Mac bloqueado." if ok else out}


def sleep_mac(**_) -> dict:
    """Put the Mac to sleep."""
    ok, out = _shell(["pmset", "sleepnow"])
    return {"ok": ok, "result": "Durmiendo el Mac." if ok else out}


def empty_trash(**_) -> dict:
    """Empty the trash. Returns confirmation request — does not auto-empty."""
    return {"ok": False, "result": "Por seguridad, vacía la papelera tú directamente desde el Finder."}


def send_notification(title: str, message: str = "", **_) -> dict:
    """Send a macOS notification."""
    safe_t = title.replace('"', '\\"')
    safe_m = message.replace('"', '\\"')
    script = f'display notification "{safe_m}" with title "{safe_t}"'
    ok, out = _osascript(script)
    return {"ok": ok, "result": "Notificación enviada." if ok else out}


def screenshot_to_clipboard(**_) -> dict:
    """Take a screenshot and put it on the clipboard via Quartz."""
    import tempfile, os
    tmp = tempfile.mktemp(suffix=".png")
    try:
        import Quartz
        image = Quartz.CGDisplayCreateImage(Quartz.CGMainDisplayID())
        url = Quartz.CFURLCreateWithFileSystemPath(None, tmp, Quartz.kCFURLPOSIXPathStyle, False)
        dest = Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
        Quartz.CGImageDestinationAddImage(dest, image, None)
        Quartz.CGImageDestinationFinalize(dest)
        # Copy to clipboard with osascript
        _osascript(f'set the clipboard to (read (POSIX file "{tmp}") as «class PNGf»)')
        return {"ok": True, "result": "Captura copiada al portapapeles."}
    except Exception as e:
        return {"ok": False, "result": str(e)}
    finally:
        try: os.unlink(tmp)
        except: pass


# ── INFO TOOLS (web-based, no API key) ─────────────────────

def weather(location: str = "", **_) -> dict:
    """Get weather using wttr.in (no API key needed)."""
    import requests
    loc = location.replace(" ", "+") or "auto"
    try:
        r = requests.get(f"https://wttr.in/{loc}?format=%l:+%C+%t+(feels+%f),+%w,+humidity+%h", timeout=10)
        if r.ok and r.text:
            return {"ok": True, "result": r.text.strip()}
    except Exception as e:
        return {"ok": False, "result": str(e)}
    return {"ok": False, "result": "No pude obtener el tiempo."}


def translate(text: str, target: str = "en", **_) -> dict:
    """Translate text via Lingva (free, no key)."""
    import requests
    try:
        # Detect source automatically
        r = requests.get(
            f"https://lingva.ml/api/v1/auto/{target}/{requests.utils.quote(text)}",
            timeout=10
        )
        if r.ok:
            data = r.json()
            return {"ok": True, "result": data.get("translation", "").strip() or text}
    except Exception:
        pass
    # Fallback: Google Translate via translate.google.com (lightweight)
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": text},
            timeout=10
        )
        if r.ok:
            j = r.json()
            return {"ok": True, "result": "".join(seg[0] for seg in j[0])}
    except Exception as e:
        return {"ok": False, "result": str(e)}
    return {"ok": False, "result": "No pude traducir."}


def define_word(word: str, **_) -> dict:
    """Look up a word in the free dictionary API."""
    import requests
    try:
        r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=10)
        if r.ok:
            j = r.json()
            entry = j[0]
            meanings = entry.get("meanings", [])
            if meanings:
                first = meanings[0]
                pos = first.get("partOfSpeech", "")
                defs = first.get("definitions", [])
                if defs:
                    return {"ok": True, "result": f"{word} ({pos}): {defs[0].get('definition', '')}"}
    except Exception as e:
        return {"ok": False, "result": str(e)}
    return {"ok": False, "result": f"No encontré '{word}'."}


def wikipedia_summary(topic: str, lang: str = "es", **_) -> dict:
    """Get a Wikipedia summary, with search fallback if direct page not found."""
    import requests
    # 1. Try direct lookup
    try:
        r = requests.get(
            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(topic)}",
            timeout=10, headers={"User-Agent": "JeffreyAssistant/1.0"}
        )
        if r.ok:
            extract = r.json().get("extract", "")
            if extract:
                return {"ok": True, "result": extract[:600]}
    except Exception:
        pass

    # 2. Fall back to search API
    try:
        r = requests.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": topic, "format": "json"},
            timeout=10, headers={"User-Agent": "JeffreyAssistant/1.0"}
        )
        if r.ok:
            results = r.json().get("query", {}).get("search", [])
            if results:
                title = results[0]["title"]
                r2 = requests.get(
                    f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(title)}",
                    timeout=10, headers={"User-Agent": "JeffreyAssistant/1.0"}
                )
                if r2.ok:
                    extract = r2.json().get("extract", "")
                    if extract:
                        return {"ok": True, "result": f"{title}: {extract[:550]}"}
    except Exception as e:
        return {"ok": False, "result": str(e)}

    return {"ok": False, "result": f"No encontré '{topic}' en Wikipedia."}


def calculate(expression: str, **_) -> dict:
    """Evaluate a math expression safely."""
    import math
    safe = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    safe.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum})
    try:
        # Disallow anything dodgy
        if any(c in expression for c in ["__", "import", "open", "exec", "eval"]):
            return {"ok": False, "result": "Expresión no permitida."}
        result = eval(expression, {"__builtins__": {}}, safe)
        return {"ok": True, "result": f"{expression} = {result}"}
    except Exception as e:
        return {"ok": False, "result": f"Error: {e}"}


def currency_convert(amount: float, src: str, dst: str, **_) -> dict:
    """Convert currency using exchangerate-api (free)."""
    import requests
    try:
        r = requests.get(f"https://api.exchangerate-api.com/v4/latest/{src.upper()}", timeout=10)
        if r.ok:
            rates = r.json().get("rates", {})
            rate = rates.get(dst.upper())
            if rate:
                converted = amount * rate
                return {"ok": True, "result": f"{amount} {src.upper()} = {converted:.2f} {dst.upper()}"}
    except Exception as e:
        return {"ok": False, "result": str(e)}
    return {"ok": False, "result": "No pude obtener el cambio."}


# ── LOCAL AI UTILITIES ─────────────────────────────────────

def grant_app_permissions(**_) -> dict:
    """Probe every installed app to trigger Automation permission dialogs in bulk."""
    import os
    script_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "grant_all_permissions.py"
    )
    venv_python = os.path.expanduser("~/Desktop/ServiceBosch/Jeffrey/Core/.venv/bin/python")
    try:
        subprocess.Popen([venv_python, script_path])
        return {"ok": True, "result": "Disparando permisos para todas las apps. Aprueba los diálogos que vayan saliendo y luego revisa System Settings → Privacy → Automation."}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def open_system_settings(pane: str = "automation", **_) -> dict:
    """Open a System Settings privacy pane directly."""
    panes = {
        "automation":       "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation",
        "accessibility":    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
        "screen":           "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
        "microphone":       "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
        "camera":           "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera",
        "files":            "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles",
        "input_monitoring": "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
    }
    url = panes.get(pane, panes["automation"])
    ok, _ = _shell(["open", url])
    return {"ok": ok, "result": f"Abriendo System Settings → {pane}." if ok else "No pude abrir Settings."}


def summarize_text(text: str = "", source: str = "clipboard", **_) -> dict:
    """Summarize text using local LLM. source: 'clipboard' or 'param'."""
    import requests
    if source == "clipboard" and not text:
        ok, clip = _shell(["pbpaste"])
        if not ok or not clip.strip():
            return {"ok": False, "result": "Portapapeles vacío."}
        text = clip[:6000]
    if not text.strip():
        return {"ok": False, "result": "Nada que resumir."}
    try:
        r = requests.post("http://localhost:11434/api/generate", json={
            "model": "llama3.2:3b",
            "prompt": f"Summarize this text in 2-3 sentences in the same language:\n\n{text}",
            "stream": False,
        }, timeout=60)
        if r.ok:
            return {"ok": True, "result": r.json().get("response", "").strip()}
    except Exception as e:
        return {"ok": False, "result": str(e)}
    return {"ok": False, "result": "Falló el resumen."}


# ── DISPATCHER ─────────────────────────────────────────────

TOOL_MAP = {
    # core
    "open_app":         open_app,
    "quit_app":         quit_app,
    "open_url":         open_url,
    "switch_desktop":   switch_desktop,
    "play_spotify":     play_spotify,
    "set_volume":       set_volume,
    "type_text":        type_text,
    "run_shell":        run_shell,
    "run_shortcut":     run_shortcut,
    "list_shortcuts":   list_shortcuts,
    "get_time":         get_current_time,
    "read_clipboard":   read_clipboard,
    "write_clipboard":  write_clipboard,
    "read_screen":      read_screen,
    "web_search":       web_search,
    # files
    "list_files":       list_files,
    "read_file":        read_file,
    "write_file":       write_file,
    "search_files":     search_files,
    # calendar / reminders
    "list_calendar_events": list_calendar_events,
    "create_calendar_event": create_calendar_event,
    "list_reminders":   list_reminders,
    "create_reminder":  create_reminder,
    # messaging
    "send_imessage":    send_imessage,
    "compose_email":    compose_email,
    # notes
    "create_note":      create_note,
    "append_to_note":   append_to_note,
    # system info
    "battery_info":     battery_info,
    "wifi_info":        wifi_info,
    "disk_space":       disk_space,
    "public_ip":        public_ip,
    "running_apps_list": running_apps_list,
    "current_track":    current_track,
    # system control
    "lock_screen":      lock_screen,
    "sleep_mac":        sleep_mac,
    "send_notification": send_notification,
    "screenshot_to_clipboard": screenshot_to_clipboard,
    # info / web
    "weather":          weather,
    "translate":        translate,
    "define_word":      define_word,
    "wikipedia_summary": wikipedia_summary,
    "calculate":        calculate,
    "currency_convert": currency_convert,
    # local AI
    "summarize_text":   summarize_text,
    # permissions
    "grant_app_permissions": grant_app_permissions,
    "open_system_settings":  open_system_settings,
}

# ── Merge in the 40+ extra power tools ─────────────────────
try:
    from jeffrey.tools_extra import EXTRA_TOOLS
    TOOL_MAP.update(EXTRA_TOOLS)
except Exception as _e:
    print(f"[jeffrey] tools_extra no cargado: {_e}")


def execute(action: dict) -> dict:
    """Execute a parsed action dict. Returns {"ok": bool, "result": str}."""
    name = action.get("action", "")
    fn = TOOL_MAP.get(name)
    if not fn:
        return {"ok": False, "result": f"Herramienta '{name}' no existe."}
    try:
        return fn(**action)
    except Exception as e:
        return {"ok": False, "result": f"Error ejecutando {name}: {e}"}


def list_tools() -> list[str]:
    return list(TOOL_MAP.keys())
