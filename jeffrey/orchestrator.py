from jeffrey.brain import chat, chat_with_tool_result, is_ollama_running, is_gemini_configured, is_nvidia_configured, is_any_cloud_configured, DEFAULT_MODEL

# Re-export for consumers (e.g. jeffrey_chat.py)
__all__ = ["process", "reset_memory", "is_gemini_configured", "is_nvidia_configured", "is_any_cloud_configured"]
from jeffrey.memory import ConversationMemory
from jeffrey.tts import speak
from jeffrey.tools import execute
import subprocess

memory = ConversationMemory(max_turns=10)


def process(user_text: str, speak_response: bool = True, model: str = DEFAULT_MODEL) -> str:
    """
    Core pipeline: user text → Gemini (primary) / Ollama (fallback) → tool or text → speak.
    Returns the final response string.
    """
    if not user_text.strip():
        return ""

    print(f"\n[jeffrey] You: {user_text}")

    # Allow running if any cloud backend configured, even if Ollama offline
    if not is_any_cloud_configured() and not is_ollama_running():
        msg = "Sin backend disponible. Añade NVIDIA o Gemini key, o ejecuta: ollama serve"
        if speak_response:
            speak(msg)
        return msg

    history = memory.get()
    result = chat(user_text, history=history, model=model)

    # ── Tool call ──────────────────────────────────────────────────────────
    if result["tool_call"]:
        action = result["tool_call"]
        action_name = action.get("action", "?")
        print(f"[jeffrey] Tool call: {action}")

        tool_result = execute(action)
        ok          = tool_result.get("ok", False)
        raw_output  = tool_result.get("result", "Hecho.")

        print(f"[jeffrey] Tool result: {raw_output[:120]}")

        # Bring Jeffrey back if read_screen hid it
        if action_name == "read_screen":
            subprocess.run(
                ["osascript", "-e", 'tell application "Jeffrey" to activate'],
                capture_output=True, timeout=3
            )

        if ok:
            # Most tools already return readable Spanish → use it directly (fast, 1 LLM call).
            # Only narrate raw-data tools that benefit from phrasing.
            NARRATE = {"web_search", "wikipedia_summary", "read_screen", "read_file",
                       "youtube_transcript", "news_briefing", "hackernews_top"}
            if action_name in NARRATE and len(raw_output) > 160:
                final = chat_with_tool_result(
                    user_text, action_name, raw_output, history=history, model=model
                )
            else:
                final = raw_output
        else:
            final = f"No pude hacer eso, Mr Bosch: {raw_output}"

        memory.add("user", user_text)
        memory.add("assistant", final)

        print(f"[jeffrey] Jeffrey: {final}")
        if speak_response:
            speak(final)
        return final

    # ── Normal text response ───────────────────────────────────────────────
    final = result["text"] or "No he entendido."
    memory.add("user", user_text)
    memory.add("assistant", final)

    print(f"[jeffrey] Jeffrey: {final}")
    if speak_response:
        speak(final)
    return final


def reset_memory() -> None:
    memory.clear()
    print("[jeffrey] Memory cleared.")
