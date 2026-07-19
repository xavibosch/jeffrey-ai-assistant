#!/usr/bin/env python3
"""
Jeffrey — Permission Bootstrap

Probes every installed Mac app with a harmless osascript so that macOS
queues up the Automation permission dialog for ALL of them at once.

Run this ONCE after installing Jeffrey. You will see a flurry of
"Jeffrey wants to control X" dialogs — click OK on each. After that
Jeffrey has full Automation access to every app forever.

Apps macOS won't let you control silently still need a one-time click
in System Settings → Privacy & Security → Automation.
"""
import os
import sys
import subprocess
import time

sys.path.insert(0, os.path.dirname(__file__))
from jeffrey.app_discovery import get_installed_apps


PROBE_SCRIPT_TEMPLATE = '''
tell application "{app}"
    try
        return name
    end try
end tell
'''


def probe(app: str) -> tuple[bool, str]:
    """Send a harmless osascript probe — macOS triggers Automation prompt."""
    script = PROBE_SCRIPT_TEMPLATE.format(app=app.replace('"', '\\"'))
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=4
        )
        if r.returncode == 0:
            return True, "ok"
        err = (r.stderr or r.stdout).strip().lower()
        if "not authorized" in err or "needs permission" in err:
            return False, "needs permission"
        if "can't get application" in err or "not running" in err:
            return False, "not installable via apple events"
        return False, err[:80]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


# Apps that don't accept Apple Events (skip them)
SKIP = {
    "Activity Monitor", "App Store", "Audio MIDI Setup", "Bluetooth File Exchange",
    "Boot Camp Assistant", "ColorSync Utility", "Console", "Digital Color Meter",
    "Disk Utility", "Grapher", "Migration Assistant", "Screen Sharing",
    "Screenshot", "System Information", "Time Machine", "VoiceOver Utility",
}


def main():
    apps = get_installed_apps()
    print(f"Encontradas {len(apps)} apps. Probando permisos para todas...\n")
    print("⚠️  Verás muchos diálogos pidiendo permiso. Pulsa OK en cada uno.\n")

    granted = []
    pending = []
    skipped = []

    for app in apps:
        if app in SKIP or app.startswith("."):
            skipped.append(app)
            continue
        ok, msg = probe(app)
        if ok:
            granted.append(app)
            print(f"✓ {app}")
        else:
            pending.append((app, msg))
            print(f"… {app} — {msg}")
        time.sleep(0.05)  # let TCC dialogs queue

    print()
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Resumen:")
    print(f"  ✓ Concedidas: {len(granted)}")
    print(f"  … Pendientes: {len(pending)}")
    print(f"  - Saltadas:   {len(skipped)}")
    print()

    if pending:
        print("Para conceder las pendientes manualmente:")
        print("  System Settings → Privacy & Security → Automation")
        print("  Busca 'Python' o 'Jeffrey' y activa los toggles.")
        print()
        print("Abriendo System Settings ahora...")
        subprocess.Popen([
            "open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation"
        ])


if __name__ == "__main__":
    main()
