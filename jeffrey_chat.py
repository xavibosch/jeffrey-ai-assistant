#!/usr/bin/env python3
"""Jeffrey interactive terminal chat."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# Suppress internal [jeffrey] debug logs for a clean chat experience
# Set JEFFREY_DEBUG=1 to see them
DEBUG = os.environ.get("JEFFREY_DEBUG", "0") == "1"

if not DEBUG:
    import builtins
    _real_print = builtins.print
    def _filtered_print(*args, **kwargs):
        msg = " ".join(str(a) for a in args)
        if msg.startswith("[jeffrey]"):
            return  # swallow internal logs
        _real_print(*args, **kwargs)
    builtins.print = _filtered_print

from jeffrey.orchestrator import process, reset_memory, is_nvidia_configured, is_gemini_configured

# Show active backend chain
parts = []
if is_nvidia_configured(): parts.append("NVIDIA Nemotron-70B")
if is_gemini_configured(): parts.append("Gemini 2.0 Flash")
parts.append("Ollama")
backend = " → ".join(parts)

print(f"Jeffrey listo [{backend}].")
print("Escribe 'salir' para cerrar, 'reset' para borrar memoria.\n")

while True:
    try:
        user = input("Tú: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nHasta luego, Mr Bosch.")
        break

    if not user:
        continue
    if user.lower() in ("salir", "exit", "quit"):
        print("Hasta luego, Mr Bosch.")
        break
    if user.lower() == "reset":
        reset_memory()
        print("Memoria borrada.\n")
        continue

    response = process(user, speak_response=False)
    print(f"\nJeffrey: {response}\n")
