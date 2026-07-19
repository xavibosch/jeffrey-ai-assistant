import json
import os
from pathlib import Path

MEMORY_DIR = Path.home() / ".jeffrey"
MEMORY_FILE = MEMORY_DIR / "memory.json"
MAX_PERSIST = 40  # max messages kept on disk (20 turns)


class ConversationMemory:
    """
    Conversation memory that persists across sessions.
    Stored at ~/.jeffrey/memory.json
    Last max_turns turns are sent to the LLM each call.
    Last MAX_PERSIST messages are saved to disk.
    """

    def __init__(self, max_turns: int = 10):
        self._max_turns = max_turns
        self._history: list[dict] = []
        self._load()

    # ── persistence ────────────────────────────────────────

    def _load(self) -> None:
        try:
            MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            if MEMORY_FILE.exists():
                data = json.loads(MEMORY_FILE.read_text())
                if isinstance(data, list):
                    self._history = data[-MAX_PERSIST:]
        except Exception:
            self._history = []

    def _save(self) -> None:
        try:
            MEMORY_DIR.mkdir(parents=True, exist_ok=True)
            MEMORY_FILE.write_text(json.dumps(self._history, ensure_ascii=False, indent=2))
        except Exception:
            pass  # never crash because of memory save

    # ── public API ─────────────────────────────────────────

    def add(self, role: str, content: str) -> None:
        self._history.append({"role": role, "content": content})
        # Trim in-memory list to MAX_PERSIST
        if len(self._history) > MAX_PERSIST:
            self._history = self._history[-MAX_PERSIST:]
        self._save()

    def get(self) -> list[dict]:
        """Return last max_turns*2 messages to send to LLM."""
        return self._history[-(self._max_turns * 2):].copy()

    def clear(self) -> None:
        self._history = []
        try:
            MEMORY_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    def __len__(self) -> int:
        return len(self._history)
