import sounddevice as sd
import numpy as np
import wave
import tempfile
import os
from pathlib import Path

SAMPLE_RATE = 48000       # record at native macOS rate, resample later for Whisper
WHISPER_RATE = 16000      # what Whisper expects
CHANNELS = 1
CHUNK_DURATION = 0.1      # seconds per chunk (100ms)
SILENCE_THRESHOLD = 0.003 # RMS below this = silence — calibrated for MacBook mic
SILENCE_DURATION = 1.0    # seconds of silence before stopping
MAX_DURATION = 12         # max recording seconds (snappier; was 30)


def record_until_silence(
    silence_threshold: float = SILENCE_THRESHOLD,
    silence_duration: float = SILENCE_DURATION,
    max_duration: float = MAX_DURATION,
    sample_rate: int = SAMPLE_RATE,
    on_speaking: callable = None,
    on_silence: callable = None,
) -> str | None:
    """
    Record audio until the user stops speaking.
    Returns path to a temp WAV file, or None on error.
    Caller is responsible for deleting the file.
    """
    chunk_size = int(sample_rate * CHUNK_DURATION)
    frames = []
    silent_chunks = 0
    silent_chunks_needed = int(silence_duration / CHUNK_DURATION)
    max_chunks = int(max_duration / CHUNK_DURATION)
    speaking_started = False

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=CHANNELS,
            dtype="float32",
            blocksize=chunk_size,
        ) as stream:
            for _ in range(max_chunks):
                chunk, _ = stream.read(chunk_size)
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                frames.append(chunk.copy())

                if rms > silence_threshold:
                    silent_chunks = 0
                    if not speaking_started:
                        speaking_started = True
                        if on_speaking:
                            on_speaking()
                else:
                    if speaking_started:
                        silent_chunks += 1
                        if on_silence:
                            on_silence(silent_chunks, silent_chunks_needed)
                        if silent_chunks >= silent_chunks_needed:
                            break  # user stopped speaking

    except Exception as e:
        print(f"[recorder] Error: {e}")
        return None

    if not frames or not speaking_started:
        return None

    # Concatenate all recorded frames
    audio_data = np.concatenate(frames, axis=0)

    # Resample from 48kHz → 16kHz for Whisper (simple decimation, good enough)
    if sample_rate != WHISPER_RATE:
        ratio = sample_rate // WHISPER_RATE  # 48000/16000 = 3
        audio_data = audio_data[::ratio]

    audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(WHISPER_RATE)
        wf.writeframes(audio_int16.tobytes())

    return tmp.name


# ── Push-to-talk: manual start/stop recording ────────────────────────────────
import threading

_ptt_lock    = threading.Lock()
_ptt_thread  = None
_ptt_stop    = None
_ptt_frames  = None


def _ptt_loop(stop_event, sample_rate):
    global _ptt_frames
    chunk_size = int(sample_rate * CHUNK_DURATION)
    frames = []
    try:
        with sd.InputStream(samplerate=sample_rate, channels=CHANNELS,
                            dtype="float32", blocksize=chunk_size) as stream:
            max_chunks = int(60 / CHUNK_DURATION)   # hard cap 60s
            for _ in range(max_chunks):
                if stop_event.is_set():
                    break
                chunk, _ = stream.read(chunk_size)
                frames.append(chunk.copy())
    except Exception as e:
        print(f"[recorder] PTT error: {e}")
    _ptt_frames = frames


def start_recording(sample_rate: int = SAMPLE_RATE) -> bool:
    """Begin recording now (push-to-talk press). Non-blocking. Returns True if started."""
    global _ptt_thread, _ptt_stop, _ptt_frames
    with _ptt_lock:
        if _ptt_thread and _ptt_thread.is_alive():
            return False  # already recording
        _ptt_stop   = threading.Event()
        _ptt_frames = None
        _ptt_thread = threading.Thread(target=_ptt_loop, args=(_ptt_stop, sample_rate), daemon=True)
        _ptt_thread.start()
        return True


def stop_recording(sample_rate: int = SAMPLE_RATE) -> str | None:
    """Stop recording (push-to-talk release), write WAV, return path (or None)."""
    global _ptt_thread, _ptt_stop, _ptt_frames
    with _ptt_lock:
        if not _ptt_thread:
            return None
        _ptt_stop.set()
        _ptt_thread.join(timeout=5)
        frames = _ptt_frames
        _ptt_thread = None

    if not frames:
        return None
    audio_data = np.concatenate(frames, axis=0)
    if sample_rate != WHISPER_RATE:
        ratio = sample_rate // WHISPER_RATE
        audio_data = audio_data[::ratio]
    audio_int16 = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(WHISPER_RATE)
        wf.writeframes(audio_int16.tobytes())
    return tmp.name


def get_input_devices() -> list[dict]:
    """List available input devices."""
    devices = sd.query_devices()
    return [
        {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
        for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]
