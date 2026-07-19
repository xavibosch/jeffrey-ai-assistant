#!/usr/bin/env python3
"""
Jeffrey — Tool Smoke Test
Runs every tool with safe sample args and prints OK / FAIL / SKIP.
Usage:  .venv/bin/python test_all_tools.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from jeffrey.tools import execute, list_tools

# Destructive / disruptive — skipped by default (would close apps, sleep Mac, etc.)
SKIP = {
    "quit_app", "lock_screen", "sleep_mac", "empty_trash", "clean_downloads",
    "bluetooth_toggle", "brightness_set", "caffeinate_mac", "grant_app_permissions",
    "open_system_settings", "switch_desktop", "type_text", "find_my_iphone",
    "run_shell", "write_file", "send_imessage", "compose_email",
    "create_calendar_event", "create_reminder", "create_note", "append_to_note",
    "record_screen", "record_audio", "take_photo", "ocr_screen_region", "color_pick",
    "focus_mode", "set_volume", "remove_background",
    # heavy (load Ollama / download / may hang) — test manually
    "summarize_text", "generate_image", "youtube_transcript",
}

# Safe sample arguments per tool
ARGS = {
    "open_app":          {"app": "Finder"},
    "open_url":          {"url": "https://example.com"},
    "play_spotify":      {"action": "status"},
    "get_time":          {},
    "read_clipboard":    {},
    "write_clipboard":   {"text": "jeffrey test"},
    "read_screen":       {"question": "test", "app": "Finder"},
    "web_search":        {"query": "barcelona weather"},
    "list_files":        {"path": "~"},
    "read_file":         {"path": "~/.jeffrey/persona.md"},
    "search_files":      {"query": "persona"},
    "list_calendar_events": {"days": 1},
    "list_reminders":    {},
    "battery_info":      {},
    "wifi_info":         {},
    "disk_space":        {},
    "public_ip":         {},
    "running_apps_list": {},
    "current_track":     {},
    "send_notification": {"title": "Jeffrey", "message": "test ok"},
    "screenshot_to_clipboard": {},
    "weather":           {"location": "Barcelona"},
    "translate":         {"text": "hola mundo", "target": "en"},
    "define_word":       {"word": "computer"},
    "wikipedia_summary": {"topic": "Albert Einstein"},
    "calculate":         {"expression": "2*21"},
    "currency_convert":  {"amount": 100, "src": "EUR", "dst": "USD"},
    "summarize_text":    {"text": "Jeffrey is a Mac assistant that does many things.", "source": "param"},
    "list_shortcuts":    {},
    "run_shortcut":      {"name": "NoExisteJeffreyTest"},   # expected fail = handled
    # extra tools
    "crypto_price":      {"symbol": "btc"},
    "stock_price":       {"symbol": "AAPL"},
    "hackernews_top":    {"count": 3},
    "reddit_top":        {"subreddit": "popular", "count": 3},
    "news_briefing":     {},
    "github_repo_stats": {"repo": "ollama/ollama"},
    "movie_info":        {"title": "Inception"},
    "sports_scores":     {"team": "Barcelona"},
    "youtube_transcript":{"url": "https://youtu.be/dQw4w9WgXcQ"},
    "generate_image":    {"prompt": "a tiny test icon"},
    "generate_qr":       {"text": "https://example.com"},
    "git_status_all":    {"base": "~/Desktop/JEFFREY"},
    "run_test":          {"path": "~"},
    "json_format":       {},
    "regex_test":        {"pattern": r"\d+", "text": "abc 123 def"},
    "generate_password": {"length": 16},
    "hash_text":         {"text": "hola", "algo": "sha256"},
    "base64_tool":       {"text": "hola", "mode": "encode"},
    "generate_uuid":     {},
    "mac_stats":         {},
    "airpods_battery":   {},
    "window_arrange":    {"position": "left"},
    "find_large_files":  {"base": "~/Desktop", "min_gb": 2},
    "roll_dice":         {"sides": 20},
    "flip_coin":         {},
    "magic_8ball":       {"question": "test?"},
    "random_fact":       {},
    "tell_joke":         {},
    "ascii_art":         {"text": "Hi"},
}

GREEN, RED, YELLOW, GREY, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[90m", "\033[0m"

def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    tools = list_tools()
    ok = fail = skip = 0
    print(f"\nProbando {len(tools)} tools...\n")
    for name in sorted(tools):
        if only and only not in name:
            continue
        if name in SKIP:
            print(f"{GREY}SKIP{RESET} {name:22} (destructivo/manual)")
            skip += 1
            continue
        args = dict(ARGS.get(name, {}))
        args["action"] = name
        t0 = time.time()
        try:
            r = execute(args)
            ms = int((time.time() - t0) * 1000)
            if r.get("ok"):
                out = (r.get("result", "") or "").replace("\n", " ")[:60]
                print(f"{GREEN}OK  {RESET} {name:22} {ms:5}ms  {out}")
                ok += 1
            else:
                out = (r.get("result", "") or "").replace("\n", " ")[:60]
                print(f"{RED}FAIL{RESET} {name:22} {ms:5}ms  {out}")
                fail += 1
        except Exception as e:
            print(f"{RED}ERR {RESET} {name:22}        {e}")
            fail += 1

    print(f"\n{'━'*60}")
    print(f"{GREEN}OK: {ok}{RESET}   {RED}FAIL: {fail}{RESET}   {GREY}SKIP: {skip}{RESET}")
    print(f"\nNota: FAIL puede ser falta de binario (ffmpeg, imagesnap) o sin")
    print(f"datos (airpods desconectados). No siempre es un bug real.\n")

if __name__ == "__main__":
    main()
