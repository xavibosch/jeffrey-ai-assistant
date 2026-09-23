from jeffrey.brain import (
    chat, chat_with_tool_result, is_ollama_running,
    is_gemini_configured, is_nvidia_configured, is_any_cloud_configured,
    DEFAULT_MODEL,
)

# Re-export for consumers (e.g. jeffrey_chat.py)
__all__ = ["process", "reset_memory", "is_gemini_configured",
           "is_nvidia_configured", "is_any_cloud_configured"]

from jeffrey.memory import ConversationMemory
from jeffrey.tts import speak, speak_async
from jeffrey.tools import execute
import subprocess

memory = ConversationMemory(max_turns=10)

# How many chained tool calls a single request may trigger
# ("abre safari y busca instagram" = 2 steps).
MAX_STEPS = 3

# Tools whose raw output reads badly out loud and benefits from the LLM phrasing it.
NARRATE = {"web_search", "wikipedia_summary", "read_screen", "read_file",
           "youtube_transcript", "news_briefing", "hackernews_top"}

# Words that signal "more than one action in this sentence". Only these requests
# pay the cost of the extra follow-up LLM call; simple orders stay fast.
_COMPOUND_MARKERS = (
    " y ", " e ", " and ", ",", " luego", " después", " despues", " then ",
    " tambien", " también", " ademas", " además", " y luego", " y despues",
)


def _looks_compound(text: str) -> bool:
    """True if the request likely contains several chained actions."""
    low = f" {text.lower().strip()} "
    return any(m in low for m in _COMPOUND_MARKERS)


def _run_tool(action: dict) -> tuple[bool, str, str]:
    """Execute one tool call. Returns (ok, output, action_name)."""
    action_name = action.get("action", "?")
    print(f"[jeffrey] Tool call: {action}")
    result = execute(action)
    ok  = result.get("ok", False)
    out = result.get("result", "Hecho.")
    print(f"[jeffrey] Tool result: {out[:120]}")

    # read_screen hides Jeffrey to see what's behind — bring it back.
    if action_name == "read_screen":
        subprocess.run(
            ["osascript", "-e", 'tell application "Jeffrey" to activate'],
            capture_output=True, timeout=3,
        )
    return ok, out, action_name


def process(user_text: str, speak_response: bool = True, model: str = DEFAULT_MODEL) -> str:
    """
    Core pipeline: user text → LLM → tool(s) → spoken answer.

    Supports COMPOUND requests: after each tool runs, the model is asked whether
    anything from the original request is still pending, up to MAX_STEPS.
    That's what makes "abre safari y busca instagram" do both things.
    """
    if not user_text.strip():
        return ""

    print(f"\n[jeffrey] You: {user_text}")

    if not is_any_cloud_configured() and not is_ollama_running():
        msg = "Sin backend disponible. Añade NVIDIA o Gemini key, o ejecuta: ollama serve"
        if speak_response:
            speak(msg)
        return msg

    history  = memory.get()
    outputs: list[str] = []          # what to tell the user at the end
    done_desc: list[str] = []        # what has already been done (for the model)
    seen: set[str] = set()           # signatures of already-executed calls
    done_names: list[str] = []       # tool names already run (excluded next step)
    prompt = user_text

    # Simple orders run in a single step — no follow-up call, no extra latency.
    max_steps = MAX_STEPS if _looks_compound(user_text) else 1

    for step in range(max_steps):
        result = chat(prompt, history=history, model=model,
                      exclude_tools=set(done_names),
                      # step 0 and 1 force a call (there is usually pending work);
                      # from step 2 on, let the model say "nothing left" instead of
                      # inventing a random action.
                      allow_no_tool=step >= 2)
        action = result.get("tool_call")

        # No tool → the model is answering with text; we're finished.
        if not action:
            text = (result.get("text") or "").strip()
            if text and not outputs:
                outputs.append(text)
            break

        # Small models like to repeat the first call. Same call twice = done.
        signature = repr(sorted(action.items()))
        if signature in seen:
            print("[jeffrey] Acción repetida → fin de la cadena")
            break
        seen.add(signature)

        ok, raw_output, action_name = _run_tool(action)

        if ok:
            if action_name in NARRATE and len(raw_output) > 160:
                piece = chat_with_tool_result(
                    user_text, action_name, raw_output, history=history, model=model
                )
            else:
                piece = raw_output
        else:
            piece = f"No pude hacer eso, Mr Bosch: {raw_output}"

        outputs.append(piece)
        done_desc.append(f"{action_name} → {raw_output[:80]}")
        done_names.append(action_name)

        # Last allowed step, or the tool failed → stop chaining.
        if step == max_steps - 1 or not ok:
            break

        # Ask whether the ORIGINAL request still has pending work.
        prompt = (
            f'Petición original de Mr Bosch: "{user_text}"\n'
            f'Ya ejecutado: {"; ".join(done_desc)}\n'
            "Si queda alguna acción pendiente de esa petición, llama a la siguiente "
            "herramienta AHORA. Si ya está todo hecho, responde solo con un resumen "
            "corto en una frase, sin llamar a ninguna herramienta."
        )

    final = " ".join(o for o in outputs if o).strip() or "No he entendido."

    memory.add("user", user_text)
    memory.add("assistant", final)

    print(f"[jeffrey] Jeffrey: {final}")
    if speak_response:
        speak_async(final)
    return final


def reset_memory() -> None:
    memory.clear()
    print("[jeffrey] Memory cleared.")
