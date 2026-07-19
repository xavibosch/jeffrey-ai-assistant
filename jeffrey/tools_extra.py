"""
Jeffrey — Extra Tools (40+ power tools)
Each returns {"ok": bool, "result": str}. Graceful when a binary/key missing.
"""
import subprocess, os, json, base64, hashlib, secrets, re, uuid, random, tempfile, shutil, time
from pathlib import Path

try:
    import requests
except Exception:
    requests = None


def _sh(cmd, timeout=15, shell=False):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=shell)
        return r.returncode == 0, (r.stdout.strip() or r.stderr.strip())
    except Exception as e:
        return False, str(e)


def _osa(script, timeout=10):
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout.strip() or r.stderr.strip())
    except Exception as e:
        return False, str(e)


def _has(binary):
    return shutil.which(binary) is not None


# ════════════════════════════════════════════════════════════════════
# MULTIMEDIA
# ════════════════════════════════════════════════════════════════════

def record_screen(seconds: int = 10, **_) -> dict:
    """Record the screen for N seconds → save .mov to Desktop."""
    out = os.path.expanduser(f"~/Desktop/jeffrey_screen_{int(time.time())}.mov")
    # screencapture -v records video; -V sets duration
    ok, msg = _sh(["screencapture", "-v", "-V", str(seconds), out], timeout=seconds + 15)
    if ok and os.path.exists(out):
        _sh(["open", "-R", out])
        return {"ok": True, "result": f"Grabación de {seconds}s guardada en Desktop."}
    return {"ok": False, "result": f"No pude grabar: {msg}"}


def record_audio(seconds: int = 10, **_) -> dict:
    """Record microphone audio for N seconds → .m4a on Desktop. Needs ffmpeg."""
    out = os.path.expanduser(f"~/Desktop/jeffrey_audio_{int(time.time())}.m4a")
    if _has("ffmpeg"):
        ok, msg = _sh(
            ["ffmpeg", "-y", "-f", "avfoundation", "-i", ":0", "-t", str(seconds), out],
            timeout=seconds + 15,
        )
        if ok and os.path.exists(out):
            _sh(["open", "-R", out])
            return {"ok": True, "result": f"Audio de {seconds}s guardado en Desktop."}
        return {"ok": False, "result": f"Error ffmpeg: {msg[:120]}"}
    return {"ok": False, "result": "Necesito ffmpeg. Instala: brew install ffmpeg"}


def take_photo(**_) -> dict:
    """Take a silent webcam photo → Desktop. Needs imagesnap."""
    out = os.path.expanduser(f"~/Desktop/jeffrey_photo_{int(time.time())}.jpg")
    if _has("imagesnap"):
        ok, msg = _sh(["imagesnap", "-w", "1", out], timeout=10)
        if ok and os.path.exists(out):
            _sh(["open", out])
            return {"ok": True, "result": "Foto tomada y guardada en Desktop."}
        return {"ok": False, "result": f"Error: {msg}"}
    return {"ok": False, "result": "Necesito imagesnap. Instala: brew install imagesnap"}


def ocr_screen_region(**_) -> dict:
    """Capture an interactively-selected region and OCR it (needs shortcuts 'OCR' or fallback)."""
    tmp = tempfile.mktemp(suffix=".png")
    ok, _m = _sh(["screencapture", "-i", tmp], timeout=60)
    if not ok or not os.path.exists(tmp):
        return {"ok": False, "result": "Captura cancelada."}
    # Try macOS Shortcuts 'Extract Text from Image' if user made one named "OCR"
    ok2, txt = _sh(["shortcuts", "run", "OCR", "-i", tmp, "-o", "-"], timeout=20)
    try: os.unlink(tmp)
    except: pass
    if ok2 and txt.strip():
        return {"ok": True, "result": f"Texto detectado:\n{txt.strip()[:800]}"}
    return {"ok": False, "result": "Crea un Shortcut llamado 'OCR' (Extract Text from Image) para esto."}


def color_pick(**_) -> dict:
    """Pick a screen color → HEX. Uses macOS color picker via Shortcut 'ColorPick' if present."""
    ok, out = _sh(["shortcuts", "run", "ColorPick", "-o", "-"], timeout=30)
    if ok and out.strip():
        return {"ok": True, "result": f"Color: {out.strip()}"}
    return {"ok": False, "result": "Crea Shortcut 'ColorPick' o usa Digital Color Meter."}


# ════════════════════════════════════════════════════════════════════
# REAL-TIME INFO (free APIs, no key)
# ════════════════════════════════════════════════════════════════════

def crypto_price(symbol: str = "bitcoin", **_) -> dict:
    """Live crypto price via CoinGecko (free)."""
    if not requests: return {"ok": False, "result": "requests no disponible."}
    ids = {"btc": "bitcoin", "eth": "ethereum", "sol": "solana", "ada": "cardano",
           "xrp": "ripple", "doge": "dogecoin", "bnb": "binancecoin"}
    cid = ids.get(symbol.lower(), symbol.lower())
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                         params={"ids": cid, "vs_currencies": "usd,eur", "include_24hr_change": "true"},
                         timeout=10)
        d = r.json().get(cid)
        if d:
            ch = d.get("usd_24h_change", 0)
            return {"ok": True, "result": f"{cid.upper()}: ${d['usd']:,} / {d.get('eur',0):,}€ ({ch:+.1f}% 24h)"}
    except Exception as e:
        return {"ok": False, "result": str(e)}
    return {"ok": False, "result": f"No encontré '{symbol}'."}


def stock_price(symbol: str, **_) -> dict:
    """Live stock price via Yahoo Finance (free)."""
    if not requests: return {"ok": False, "result": "requests no disponible."}
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol.upper()}",
                         timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        res = r.json()["chart"]["result"][0]["meta"]
        price = res.get("regularMarketPrice")
        prev = res.get("chartPreviousClose", price)
        ch = ((price - prev) / prev * 100) if prev else 0
        cur = res.get("currency", "USD")
        return {"ok": True, "result": f"{symbol.upper()}: {price:,.2f} {cur} ({ch:+.2f}%)"}
    except Exception as e:
        return {"ok": False, "result": f"No encontré '{symbol}': {e}"}


def hackernews_top(count: int = 5, **_) -> dict:
    """Top Hacker News stories now."""
    if not requests: return {"ok": False, "result": "requests no disponible."}
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()[:count]
        lines = []
        for i in ids:
            s = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json", timeout=10).json()
            lines.append(f"• {s.get('title','?')} ({s.get('score',0)} pts)")
        return {"ok": True, "result": "Top Hacker News:\n" + "\n".join(lines)}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def reddit_top(subreddit: str = "all", count: int = 5, **_) -> dict:
    """Top Reddit posts from a subreddit (free JSON)."""
    if not requests: return {"ok": False, "result": "requests no disponible."}
    ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
    for host in ("https://www.reddit.com", "https://old.reddit.com"):
        try:
            r = requests.get(f"{host}/r/{subreddit}/hot.json",
                             params={"limit": count}, timeout=10,
                             headers={"User-Agent": ua, "Accept": "application/json"})
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                posts = r.json()["data"]["children"]
                lines = [f"• {p['data']['title'][:90]} (↑{p['data']['ups']})" for p in posts[:count]]
                if lines:
                    return {"ok": True, "result": f"Top r/{subreddit}:\n" + "\n".join(lines)}
        except Exception:
            continue
    return {"ok": False, "result": "Reddit bloquea peticiones automáticas ahora mismo. Usa hackernews_top o news_briefing."}


def news_briefing(**_) -> dict:
    """Quick news briefing — top HN + world headlines."""
    if not requests: return {"ok": False, "result": "requests no disponible."}
    try:
        # BBC RSS via free converter
        r = requests.get("https://api.rss2json.com/v1/api.json",
                         params={"rss_url": "http://feeds.bbci.co.uk/news/world/rss.xml"}, timeout=10)
        items = r.json().get("items", [])[:5]
        lines = [f"• {it['title']}" for it in items]
        return {"ok": True, "result": "Titulares mundo (BBC):\n" + "\n".join(lines)}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def github_repo_stats(repo: str, **_) -> dict:
    """GitHub repo stats. repo = 'owner/name'."""
    if not requests: return {"ok": False, "result": "requests no disponible."}
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}", timeout=10,
                         headers={"Accept": "application/vnd.github+json"})
        d = r.json()
        if "full_name" in d:
            return {"ok": True, "result": (f"{d['full_name']}: ⭐{d['stargazers_count']:,} "
                    f"🍴{d['forks_count']:,} · issues {d['open_issues_count']} · {d.get('language','?')}")}
        return {"ok": False, "result": f"No encontré '{repo}'."}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def movie_info(title: str, **_) -> dict:
    """Movie info via iTunes Search (free); falls back to Wikipedia if not found."""
    if not requests: return {"ok": False, "result": "requests no disponible."}
    # 1) iTunes — try several storefronts (US has the widest catalog)
    for country in ("US", "ES", "GB"):
        try:
            r = requests.get("https://itunes.apple.com/search",
                             params={"term": title, "media": "movie", "limit": 1, "country": country},
                             timeout=10)
            res = r.json().get("results", [])
            if res:
                m = res[0]
                return {"ok": True, "result": (f"{m.get('trackName')} ({m.get('releaseDate','')[:4]}) — "
                        f"{m.get('primaryGenreName','')}. {m.get('longDescription','')[:300]}")}
        except Exception:
            continue
    # 2) Wikipedia fallback — guarantees an answer for well-known films
    try:
        from urllib.parse import quote
        for lang in ("es", "en"):
            r = requests.get(
                f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title + ' (película)')}",
                timeout=10, headers={"User-Agent": "JeffreyAssistant/1.0"})
            if r.status_code == 200:
                ex = r.json().get("extract", "")
                if ex:
                    return {"ok": True, "result": ex[:400]}
            r2 = requests.get(
                f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title)}",
                timeout=10, headers={"User-Agent": "JeffreyAssistant/1.0"})
            if r2.status_code == 200:
                ex = r2.json().get("extract", "")
                if ex:
                    return {"ok": True, "result": ex[:400]}
    except Exception:
        pass
    return {"ok": False, "result": f"No encontré información de '{title}'."}


# Common team name → (ESPN league, ESPN team id)
_ESPN_TEAMS = {
    # La Liga
    "barcelona": ("esp.1", 83), "barça": ("esp.1", 83), "barca": ("esp.1", 83),
    "real madrid": ("esp.1", 86), "madrid": ("esp.1", 86),
    "atletico": ("esp.1", 1068), "atletico madrid": ("esp.1", 1068), "atleti": ("esp.1", 1068),
    "sevilla": ("esp.1", 243), "valencia": ("esp.1", 94), "villarreal": ("esp.1", 102),
    "athletic": ("esp.1", 93), "bilbao": ("esp.1", 93), "real sociedad": ("esp.1", 89),
    "betis": ("esp.1", 244), "girona": ("esp.1", 9812), "getafe": ("esp.1", 2922),
    "osasuna": ("esp.1", 97), "celta": ("esp.1", 85), "rayo": ("esp.1", 101),
    "espanyol": ("esp.1", 88), "mallorca": ("esp.1", 84), "alaves": ("esp.1", 96),
    # Premier
    "arsenal": ("eng.1", 359), "chelsea": ("eng.1", 363), "liverpool": ("eng.1", 364),
    "manchester united": ("eng.1", 360), "united": ("eng.1", 360),
    "manchester city": ("eng.1", 382), "city": ("eng.1", 382),
    "tottenham": ("eng.1", 367), "newcastle": ("eng.1", 361),
    # Other big clubs
    "psg": ("fra.1", 160), "bayern": ("ger.1", 132), "dortmund": ("ger.1", 124),
    "juventus": ("ita.1", 111), "inter": ("ita.1", 110), "milan": ("ita.1", 103),
    "napoli": ("ita.1", 114),
}

def sports_scores(team: str = "", **_) -> dict:
    """Last finished match for a team via ESPN's free API (real data, no key)."""
    if not requests: return {"ok": False, "result": "requests no disponible."}
    if not team:
        return {"ok": False, "result": "Dime un equipo, ej: Barcelona."}

    key = team.lower().strip()
    entry = _ESPN_TEAMS.get(key)
    if not entry:
        # partial match
        for k, v in _ESPN_TEAMS.items():
            if k in key or key in k:
                entry = v
                break
    if not entry:
        return {"ok": False, "result": f"No tengo a '{team}' en mi lista. Equipos top: Barça, Madrid, Atleti, Sevilla, Liverpool, City, PSG, Bayern, Juventus, Inter."}

    league, tid = entry
    try:
        r = requests.get(
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{tid}/schedule",
            timeout=12,
        )
        data = r.json()
        name = data.get("team", {}).get("displayName", team)

        finished = []
        for e in data.get("events", []):
            comp = (e.get("competitions") or [{}])[0]
            if comp.get("status", {}).get("type", {}).get("completed"):
                finished.append((e.get("date", ""), comp))
        if not finished:
            return {"ok": True, "result": f"No tengo partidos terminados recientes de {name}."}

        finished.sort(key=lambda x: x[0])      # chronological
        date_iso, comp = finished[-1]          # most recent
        cs = comp.get("competitors", [])
        if len(cs) < 2:
            return {"ok": True, "result": f"Datos incompletos del último partido de {name}."}

        def label(c):
            nm = c["team"]["displayName"]
            sc = c.get("score", {})
            sc = sc.get("displayValue") if isinstance(sc, dict) else sc
            return nm, (sc if sc is not None else "-")

        (n1, s1), (n2, s2) = label(cs[0]), label(cs[1])
        date = date_iso[:10]

        ago = date
        try:
            from datetime import datetime, date as _d
            d = datetime.strptime(date, "%Y-%m-%d").date()
            days = (_d.today() - d).days
            if days <= 0:   ago = "hoy"
            elif days == 1: ago = "ayer"
            elif days < 14: ago = f"hace {days} días"
            elif days < 60: ago = f"hace {days // 7} semanas"
            else:           ago = f"hace {days // 30} meses"
        except Exception:
            pass

        return {"ok": True, "result": (
            f"Último partido de {name}: {n1} {s1}-{s2} {n2} ({ago}, {date}). "
            f"Es el más reciente que consta."
        )}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def youtube_transcript(url: str, **_) -> dict:
    """Get YouTube transcript. Needs youtube-transcript-api pip package."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception:
        return {"ok": False, "result": "Instala: pip install youtube-transcript-api"}
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url)
    if not m:
        return {"ok": False, "result": "URL de YouTube no válida."}
    try:
        t = YouTubeTranscriptApi.get_transcript(m.group(1), languages=["es", "en"])
        text = " ".join(x["text"] for x in t)
        return {"ok": True, "result": text[:3000]}
    except Exception as e:
        return {"ok": False, "result": f"Sin transcript: {e}"}


# ════════════════════════════════════════════════════════════════════
# CREATIVE AI (free)
# ════════════════════════════════════════════════════════════════════

def generate_image(prompt: str, **_) -> dict:
    """Text → image via Pollinations.ai (free, no key). Saves to Desktop + opens."""
    if not requests: return {"ok": False, "result": "requests no disponible."}
    out = os.path.expanduser(f"~/Desktop/jeffrey_img_{int(time.time())}.jpg")
    try:
        from urllib.parse import quote
        r = requests.get(f"https://image.pollinations.ai/prompt/{quote(prompt)}",
                         params={"width": 1024, "height": 1024, "nologo": "true"}, timeout=60)
        if r.ok and r.content:
            with open(out, "wb") as f:
                f.write(r.content)
            _sh(["open", out])
            return {"ok": True, "result": f"Imagen generada y guardada en Desktop: '{prompt}'."}
    except Exception as e:
        return {"ok": False, "result": str(e)}
    return {"ok": False, "result": "No pude generar la imagen."}


def generate_qr(text: str, **_) -> dict:
    """Generate a QR code → Desktop + open."""
    if not requests: return {"ok": False, "result": "requests no disponible."}
    out = os.path.expanduser(f"~/Desktop/jeffrey_qr_{int(time.time())}.png")
    try:
        from urllib.parse import quote
        r = requests.get("https://api.qrserver.com/v1/create-qr-code/",
                         params={"size": "500x500", "data": text}, timeout=15)
        if r.ok:
            with open(out, "wb") as f:
                f.write(r.content)
            _sh(["open", out])
            return {"ok": True, "result": f"QR generado en Desktop para: {text[:60]}"}
    except Exception as e:
        return {"ok": False, "result": str(e)}
    return {"ok": False, "result": "No pude generar el QR."}


def remove_background(image_path: str = "", **_) -> dict:
    """Remove image background. Needs rembg (pip install rembg)."""
    try:
        from rembg import remove
        from PIL import Image
    except Exception:
        return {"ok": False, "result": "Instala: pip install rembg pillow"}
    path = os.path.expanduser(image_path)
    if not os.path.exists(path):
        return {"ok": False, "result": "Imagen no encontrada."}
    out = path.rsplit(".", 1)[0] + "_nobg.png"
    try:
        Image.open(path).convert("RGBA")
        with open(path, "rb") as f:
            result = remove(f.read())
        with open(out, "wb") as f:
            f.write(result)
        _sh(["open", out])
        return {"ok": True, "result": f"Fondo eliminado → {out}"}
    except Exception as e:
        return {"ok": False, "result": str(e)}


# ════════════════════════════════════════════════════════════════════
# DEV POWER
# ════════════════════════════════════════════════════════════════════

def git_status_all(base: str = "~/Desktop", **_) -> dict:
    """Scan for git repos under base and report dirty ones."""
    base = os.path.expanduser(base)
    dirty = []
    for root, dirs, _files in os.walk(base):
        if ".git" in dirs:
            dirs[:] = []  # don't descend
            ok, out = _sh(["git", "-C", root, "status", "--porcelain"], timeout=10)
            name = os.path.basename(root)
            if out.strip():
                dirty.append(f"• {name}: {len(out.splitlines())} cambios sin commit")
        # skip heavy dirs
        dirs[:] = [d for d in dirs if d not in ("node_modules", ".next", "Pods", ".venv")]
    if dirty:
        return {"ok": True, "result": "Repos con cambios:\n" + "\n".join(dirty[:20])}
    return {"ok": True, "result": "Todos los repos limpios."}


def run_test(path: str = ".", **_) -> dict:
    """Auto-detect and run tests (npm test / pytest)."""
    path = os.path.expanduser(path)
    if os.path.exists(os.path.join(path, "package.json")):
        ok, out = _sh(["npm", "test"], timeout=120)
    elif os.path.exists(os.path.join(path, "pytest.ini")) or os.path.exists(os.path.join(path, "tests")):
        ok, out = _sh(["pytest", "-q"], timeout=120)
    else:
        return {"ok": False, "result": "No detecté proyecto de tests aquí."}
    return {"ok": ok, "result": out[-600:]}


def json_format(**_) -> dict:
    """Pretty-print JSON from clipboard → back to clipboard."""
    ok, clip = _sh(["pbpaste"])
    if not ok or not clip.strip():
        return {"ok": False, "result": "Portapapeles vacío."}
    try:
        obj = json.loads(clip)
        pretty = json.dumps(obj, indent=2, ensure_ascii=False)
        subprocess.run(["pbcopy"], input=pretty, text=True)
        return {"ok": True, "result": f"JSON formateado ({len(pretty)} chars) copiado al portapapeles."}
    except Exception as e:
        return {"ok": False, "result": f"JSON inválido: {e}"}


def regex_test(pattern: str, text: str, **_) -> dict:
    """Test a regex against text."""
    try:
        matches = re.findall(pattern, text)
        if matches:
            return {"ok": True, "result": f"{len(matches)} coincidencias: {matches[:10]}"}
        return {"ok": True, "result": "Sin coincidencias."}
    except Exception as e:
        return {"ok": False, "result": f"Regex inválido: {e}"}


def generate_password(length: int = 20, **_) -> dict:
    """Generate a secure random password → clipboard."""
    import string
    length = max(8, min(int(length), 128))
    alpha = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    pw = "".join(secrets.choice(alpha) for _ in range(length))
    subprocess.run(["pbcopy"], input=pw, text=True)
    return {"ok": True, "result": f"Contraseña de {length} chars copiada al portapapeles."}


def hash_text(text: str, algo: str = "sha256", **_) -> dict:
    """Hash text with md5/sha1/sha256."""
    algo = algo.lower()
    if algo not in ("md5", "sha1", "sha256", "sha512"):
        algo = "sha256"
    h = hashlib.new(algo, text.encode()).hexdigest()
    return {"ok": True, "result": f"{algo}: {h}"}


def base64_tool(text: str, mode: str = "encode", **_) -> dict:
    """Base64 encode or decode."""
    try:
        if mode == "decode":
            res = base64.b64decode(text).decode()
        else:
            res = base64.b64encode(text.encode()).decode()
        return {"ok": True, "result": res}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def generate_uuid(**_) -> dict:
    """Generate a UUID4 → clipboard."""
    u = str(uuid.uuid4())
    subprocess.run(["pbcopy"], input=u, text=True)
    return {"ok": True, "result": f"UUID: {u} (copiado)"}


# ════════════════════════════════════════════════════════════════════
# SYSTEM POWER
# ════════════════════════════════════════════════════════════════════

def mac_stats(**_) -> dict:
    """CPU load, memory, uptime."""
    ok, load = _sh(["sysctl", "-n", "vm.loadavg"])
    ok2, mem = _sh(["memory_pressure"], timeout=5)
    ok3, up = _sh(["uptime"])
    free_line = ""
    for line in (mem or "").splitlines():
        if "free percentage" in line.lower():
            free_line = line.strip()
    return {"ok": True, "result": f"Carga:{load} · {free_line or 'mem n/a'} · {up}"}


def airpods_battery(**_) -> dict:
    """Bluetooth device battery (AirPods etc.) via ioreg."""
    ok, out = _sh(["ioreg", "-r", "-l", "-k", "BatteryPercent"], timeout=10)
    if ok and out:
        pcts = re.findall(r'"BatteryPercent"\s*=\s*(\d+)', out)
        names = re.findall(r'"Product"\s*=\s*"([^"]+)"', out)
        if pcts:
            pairs = []
            for i, p in enumerate(pcts):
                nm = names[i] if i < len(names) else "dispositivo"
                pairs.append(f"{nm}: {p}%")
            return {"ok": True, "result": " · ".join(pairs)}
    return {"ok": False, "result": "No hay dispositivos Bluetooth con batería conectados."}


def window_arrange(position: str = "left", **_) -> dict:
    """Tile frontmost window: left/right/full/center."""
    script = '''
    tell application "System Events"
        set fp to first application process whose frontmost is true
        set theWindow to first window of fp
        set screenSize to size of (first window of (first application process whose name is "Finder"))
    end tell
    '''
    # Get screen resolution
    ok, res = _sh(["system_profiler", "SPDisplaysDataType"], timeout=8)
    w, h = 1440, 900
    m = re.search(r"Resolution:\s*(\d+)\s*x\s*(\d+)", res or "")
    if m:
        w, h = int(m.group(1)), int(m.group(2))
    layouts = {
        "left":   (0, 0, w // 2, h),
        "right":  (w // 2, 0, w // 2, h),
        "full":   (0, 0, w, h),
        "center": (w // 4, h // 8, w // 2, int(h * 0.75)),
    }
    x, y, ww, hh = layouts.get(position, layouts["left"])
    s = f'''
    tell application "System Events"
        set fp to first application process whose frontmost is true
        set position of front window of fp to {{{x}, {y}}}
        set size of front window of fp to {{{ww}, {hh}}}
    end tell
    '''
    ok, out = _osa(s)
    return {"ok": ok, "result": f"Ventana movida a {position}." if ok else out}


def find_large_files(base: str = "~", min_gb: float = 1.0, **_) -> dict:
    """Find largest files under base."""
    base = os.path.expanduser(base)
    ok, out = _sh(["find", base, "-type", "f", "-size", f"+{int(min_gb*1024)}M"], timeout=30)
    if not ok:
        return {"ok": False, "result": "No pude buscar."}
    files = out.splitlines()[:20]
    if not files:
        return {"ok": True, "result": f"Sin archivos mayores de {min_gb}GB."}
    sized = []
    for f in files:
        try:
            gb = os.path.getsize(f) / 1e9
            sized.append((gb, f))
        except: pass
    sized.sort(reverse=True)
    lines = [f"• {gb:.1f}GB — {os.path.basename(f)}" for gb, f in sized[:15]]
    return {"ok": True, "result": "Archivos grandes:\n" + "\n".join(lines)}


def clean_downloads(days: int = 30, **_) -> dict:
    """Move Downloads files older than N days to Trash."""
    dl = os.path.expanduser("~/Downloads")
    if not os.path.isdir(dl):
        return {"ok": False, "result": "No hay carpeta Downloads."}
    cutoff = time.time() - days * 86400
    moved = 0
    for f in os.listdir(dl):
        p = os.path.join(dl, f)
        try:
            if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                _osa(f'tell application "Finder" to delete POSIX file "{p}"')
                moved += 1
        except: pass
    return {"ok": True, "result": f"{moved} archivos de +{days} días movidos a Papelera."}


def brightness_set(level: int = 50, **_) -> dict:
    """Set screen brightness 0-100. Needs 'brightness' binary."""
    if _has("brightness"):
        val = max(0, min(int(level), 100)) / 100.0
        ok, out = _sh(["brightness", str(val)])
        return {"ok": ok, "result": f"Brillo al {level}%." if ok else out}
    return {"ok": False, "result": "Instala: brew install brightness"}


def focus_mode(mode: str = "on", **_) -> dict:
    """Toggle Do Not Disturb via Shortcut 'Focus' (mode passed as input)."""
    ok, out = _sh(["shortcuts", "run", "Focus", "-i", mode], timeout=15)
    if ok:
        return {"ok": True, "result": f"Modo concentración: {mode}."}
    return {"ok": False, "result": "Crea un Shortcut 'Focus' que active 'No molestar'."}


def caffeinate_mac(minutes: int = 60, **_) -> dict:
    """Keep Mac awake for N minutes."""
    subprocess.Popen(["caffeinate", "-d", "-t", str(int(minutes) * 60)])
    return {"ok": True, "result": f"Mac despierto durante {minutes} min."}


def bluetooth_toggle(state: str = "toggle", **_) -> dict:
    """Toggle Bluetooth. Needs blueutil."""
    if _has("blueutil"):
        arg = {"on": "1", "off": "0", "toggle": "toggle"}.get(state, "toggle")
        ok, out = _sh(["blueutil", "--power", arg])
        return {"ok": ok, "result": f"Bluetooth: {state}." if ok else out}
    return {"ok": False, "result": "Instala: brew install blueutil"}


def find_my_iphone(**_) -> dict:
    """Play sound on iPhone via Find My (needs Shortcut 'FindiPhone')."""
    ok, out = _sh(["shortcuts", "run", "FindiPhone"], timeout=15)
    if ok:
        return {"ok": True, "result": "Sonando tu iPhone."}
    return {"ok": False, "result": "Crea un Shortcut 'FindiPhone' con la acción de Buscar."}


# ════════════════════════════════════════════════════════════════════
# FUN / RANDOM
# ════════════════════════════════════════════════════════════════════

def roll_dice(sides: int = 6, count: int = 1, **_) -> dict:
    """Roll N dice of S sides."""
    sides = max(2, min(int(sides), 1000))
    count = max(1, min(int(count), 20))
    rolls = [random.randint(1, sides) for _ in range(count)]
    if count == 1:
        return {"ok": True, "result": f"🎲 {rolls[0]}"}
    return {"ok": True, "result": f"🎲 {rolls} (total {sum(rolls)})"}


def flip_coin(**_) -> dict:
    """Flip a coin."""
    return {"ok": True, "result": random.choice(["Cara", "Cruz"])}


def magic_8ball(question: str = "", **_) -> dict:
    """Magic 8-ball answer."""
    answers = ["Sí.", "No.", "Sin duda.", "Lo dudo.", "Pregunta más tarde.",
               "Definitivamente.", "No cuentes con ello.", "Probablemente sí.",
               "Mejor no te lo digo ahora.", "Todo apunta a que sí."]
    return {"ok": True, "result": f"🎱 {random.choice(answers)}"}


def random_fact(**_) -> dict:
    """A random useless fact."""
    if not requests: return {"ok": False, "result": "requests no disponible."}
    try:
        r = requests.get("https://uselessfacts.jsph.pl/api/v2/facts/random",
                         params={"language": "en"}, timeout=10)
        return {"ok": True, "result": r.json().get("text", "?")}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def tell_joke(**_) -> dict:
    """Tell a joke."""
    if not requests: return {"ok": False, "result": "requests no disponible."}
    try:
        r = requests.get("https://official-joke-api.appspot.com/random_joke", timeout=10)
        j = r.json()
        return {"ok": True, "result": f"{j.get('setup','')} … {j.get('punchline','')}"}
    except Exception as e:
        return {"ok": False, "result": str(e)}


def ascii_art(text: str, **_) -> dict:
    """Render text as ASCII art. Needs pyfiglet (optional)."""
    try:
        import pyfiglet
        return {"ok": True, "result": "\n" + pyfiglet.figlet_format(text[:20])}
    except Exception:
        return {"ok": False, "result": "Instala: pip install pyfiglet"}


# ════════════════════════════════════════════════════════════════════
# REGISTRY (name → function)
# ════════════════════════════════════════════════════════════════════

EXTRA_TOOLS = {
    # multimedia
    "record_screen": record_screen,
    "record_audio": record_audio,
    "take_photo": take_photo,
    "ocr_screen_region": ocr_screen_region,
    "color_pick": color_pick,
    # real-time info
    "crypto_price": crypto_price,
    "stock_price": stock_price,
    "hackernews_top": hackernews_top,
    "reddit_top": reddit_top,
    "news_briefing": news_briefing,
    "github_repo_stats": github_repo_stats,
    "movie_info": movie_info,
    "sports_scores": sports_scores,
    "youtube_transcript": youtube_transcript,
    # creative
    "generate_image": generate_image,
    "generate_qr": generate_qr,
    "remove_background": remove_background,
    # dev power
    "git_status_all": git_status_all,
    "run_test": run_test,
    "json_format": json_format,
    "regex_test": regex_test,
    "generate_password": generate_password,
    "hash_text": hash_text,
    "base64_tool": base64_tool,
    "generate_uuid": generate_uuid,
    # system
    "mac_stats": mac_stats,
    "airpods_battery": airpods_battery,
    "window_arrange": window_arrange,
    "find_large_files": find_large_files,
    "clean_downloads": clean_downloads,
    "brightness_set": brightness_set,
    "focus_mode": focus_mode,
    "caffeinate_mac": caffeinate_mac,
    "bluetooth_toggle": bluetooth_toggle,
    "find_my_iphone": find_my_iphone,
    # fun
    "roll_dice": roll_dice,
    "flip_coin": flip_coin,
    "magic_8ball": magic_8ball,
    "random_fact": random_fact,
    "tell_joke": tell_joke,
    "ascii_art": ascii_art,
}
