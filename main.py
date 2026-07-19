#!/usr/bin/env python3
"""
Jeffrey — Voice mode.
Triggered by the Swift hotkey helper via IPC file or run standalone.

Usage:
  python main.py              # voice REPL (press Enter to start recording)
  python main.py --once       # record once, respond, exit
  python main.py --device 1   # use specific mic device index
"""
import sys
import os
import signal

sys.path.insert(0, os.path.dirname(__file__))

from jeffrey.stt import transcribe, preload_model
from jeffrey.recorder import record_until_silence, get_input_devices
from jeffrey.orchestrator import process
from jeffrey.tts import speak
from jeffrey.brain import is_ollama_running, DEFAULT_MODEL

MIC_DEVICE = None  # None = default (MacBook Pro Microphone)


def select_macbook_mic() -> int | None:
    """Auto-select the MacBook Pro internal mic."""
    for d in get_input_devices():
        if "macbook" in d["name"].lower() or "built-in" in d["name"].lower():
            return d["index"]
    return None


def listen_and_respond(device: int | None = None) -> str | None:
    """Record voice → transcribe → respond. Returns transcribed text or None."""
    import sounddevice as sd
    import numpy as np

    print("\n[jeffrey] 🎙  Escuchando... habla ahora")
    print("[jeffrey]    (verás ██ moverse cuando te oiga)\n")

    # Show live levels while recording
    speaking_started = False
    frames = []
    silent_chunks = 0
    silent_chunks_needed = 15  # 1.5s silence
    max_chunks = 300           # 30s max

    try:
        with sd.InputStream(samplerate=48000, channels=1, dtype='float32', blocksize=4800) as stream:
            for _ in range(max_chunks):
                chunk, _ = stream.read(4800)
                rms = float(np.sqrt(np.mean(chunk**2)))
                frames.append(chunk.copy())

                bar = "█" * min(40, int(rms * 3000))
                threshold_mark = "│" if rms < 0.003 else "◀ VOZ"
                print(f"  {rms:.4f}  {bar:<40} {threshold_mark}   ", end="\r")

                if rms > 0.003:
                    silent_chunks = 0
                    if not speaking_started:
                        speaking_started = True
                        print(f"\n[jeffrey] 🔴 Voz detectada! Grabando...")
                else:
                    if speaking_started:
                        silent_chunks += 1
                        if silent_chunks >= silent_chunks_needed:
                            print(f"\n[jeffrey] ✅ Listo, procesando...")
                            break
    except Exception as e:
        print(f"\n[jeffrey] ❌ Error mic: {e}")
        return None

    if not speaking_started:
        print("\n[jeffrey] ⚠️  No detecté voz. Comprueba que hablas cerca del mic.")
        return None

    # Resample 48kHz → 16kHz for Whisper (proper anti-aliased resampling)
    from scipy.signal import resample_poly
    audio_raw = np.concatenate(frames, axis=0).flatten()
    audio = resample_poly(audio_raw, up=1, down=3).astype(np.float32)  # 48k÷3=16k
    audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)

    import wave, tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
        wf.writeframes(audio_int16.tobytes())

    print("[jeffrey] 💭 Transcribiendo con Whisper...")
    text = transcribe(tmp.name)
    os.unlink(tmp.name)

    if not text.strip():
        print("[jeffrey] ❓ No entendí nada — intenta hablar más claro.")
        return None

    print(f"[jeffrey] 📝 Transcrito: '{text}'")
    process(text, speak_response=True, model=DEFAULT_MODEL)
    return text


def main():
    once = "--once" in sys.argv
    device_idx = None

    # Parse --device flag
    if "--device" in sys.argv:
        idx = sys.argv.index("--device")
        if idx + 1 < len(sys.argv):
            device_idx = int(sys.argv[idx + 1])

    print("=" * 50)
    print("  JEFFREY — Voice Mode")
    print("=" * 50)

    if not is_ollama_running():
        print("❌ Ollama no está corriendo. Ejecuta: ollama serve")
        sys.exit(1)

    # Auto-select MacBook mic
    if device_idx is None:
        device_idx = select_macbook_mic()

    devices = get_input_devices()
    print(f"✅ Mic: {devices[device_idx]['name'] if device_idx is not None else 'default'}")
    print("✅ Cargando modelo Whisper...")
    preload_model()
    print("✅ Listo.")

    speak("Jeffrey listo. Puedes hablar.")

    if once:
        listen_and_respond(device=device_idx)
        return

    # Voice REPL
    print("\nPresiona Enter para hablar, Ctrl+C para salir.\n")
    while True:
        try:
            input("[ Enter para hablar ]")
            listen_and_respond(device=device_idx)
        except KeyboardInterrupt:
            print("\n\nHasta luego.")
            speak("Hasta luego.")
            break


if __name__ == "__main__":
    main()
