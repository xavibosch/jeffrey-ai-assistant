#!/usr/bin/env python3
"""
Jeffrey Phase 1 — Text mode test.
Usage:
  python test_text.py                    # interactive REPL
  python test_text.py "tu pregunta"      # single shot
  python test_text.py --no-voice "texto" # skip TTS
"""
import sys
import os

# Add Core to path
sys.path.insert(0, os.path.dirname(__file__))

from jeffrey.brain import is_ollama_running, list_models
from jeffrey.orchestrator import process, reset_memory
from jeffrey.brain import FAST_MODEL, DEFAULT_MODEL

def main():
    speak = True
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--no-voice" in sys.argv:
        speak = False

    # Pick model — use fast for single queries, full for REPL
    model = DEFAULT_MODEL

    print("=" * 50)
    print("  JEFFREY — Text Mode Test")
    print("=" * 50)

    # Sanity checks
    if not is_ollama_running():
        print("❌ Ollama no está corriendo. Ejecuta: ollama serve")
        sys.exit(1)

    models = list_models()
    print(f"✅ Ollama running | Models: {models}")
    print(f"✅ Using model: {model}")
    print(f"✅ TTS: {'ON (Daniel)' if speak else 'OFF'}")
    print()

    # Single-shot mode
    if args:
        query = " ".join(args)
        process(query, speak_response=speak, model=model)
        return

    # Interactive REPL
    print("Escribe algo para Jeffrey (o 'salir' para salir, 'clear' para limpiar memoria):")
    print("-" * 50)
    while True:
        try:
            user_input = input("\nTú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAdiós.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("salir", "exit", "quit"):
            print("Hasta luego.")
            break
        if user_input.lower() == "clear":
            reset_memory()
            continue

        process(user_input, speak_response=speak, model=model)


if __name__ == "__main__":
    main()
