"""
Jeffrey App Discovery
Scans installed apps dynamically — always up to date, no hardcoding.
"""
import os
import subprocess
import json
import time
from pathlib import Path

# Directories to scan
APP_DIRS = [
    "/Applications",
    "/System/Applications",
    "/System/Applications/Utilities",
    os.path.expanduser("~/Applications"),
]

_cache: list[str] = []
_cache_time: float = 0
CACHE_TTL = 60  # seconds — refresh every minute


def get_installed_apps(force: bool = False) -> list[str]:
    """
    Return sorted list of installed app names (without .app).
    Cached for 60s so it's fast on every request.
    """
    global _cache, _cache_time

    if not force and _cache and (time.time() - _cache_time) < CACHE_TTL:
        return _cache

    apps = set()
    for directory in APP_DIRS:
        if not os.path.isdir(directory):
            continue
        for entry in os.scandir(directory):
            if entry.name.endswith(".app"):
                apps.add(entry.name[:-4])  # strip .app

    # Also check Homebrew cask apps
    brew_apps = Path("/opt/homebrew/Caskroom")
    if brew_apps.exists():
        for entry in brew_apps.iterdir():
            if entry.is_dir():
                # Convert cask name to likely app name (best effort)
                apps.add(entry.name.replace("-", " ").title())

    _cache = sorted(apps, key=str.lower)
    _cache_time = time.time()
    return _cache


def get_running_apps() -> list[str]:
    """Return list of currently running app names."""
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of every application process whose background only is false'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return [a.strip() for a in result.stdout.strip().split(",") if a.strip()]
    except Exception:
        pass
    return []


def find_app(query: str) -> str | None:
    """
    Fuzzy-find an app by partial name.
    E.g. "spot" → "Spotify", "what" → "WhatsApp"
    Returns the best match or None.
    """
    query_lower = query.lower()
    apps = get_installed_apps()

    # Exact match first
    for app in apps:
        if app.lower() == query_lower:
            return app

    # Starts with
    for app in apps:
        if app.lower().startswith(query_lower):
            return app

    # Contains
    for app in apps:
        if query_lower in app.lower():
            return app

    return None


def apps_context_string() -> str:
    """
    Return a compact string listing all installed apps.
    Injected into the LLM system prompt so Jeffrey knows what's available.
    """
    apps = get_installed_apps()
    return ", ".join(apps)
