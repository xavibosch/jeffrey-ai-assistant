from faster_whisper import WhisperModel
import os

_model: WhisperModel | None = None
MODEL_SIZE = "small"  # small >> base for multilingual (Spanish + English), ~2s on Apple Silicon


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        print("[stt] Loading Whisper model (first time may take a few seconds)...")
        _model = WhisperModel(
            MODEL_SIZE,
            device="cpu",          # use 'cuda' if you had a GPU
            compute_type="int8",   # fastest on CPU, good quality
        )
        print("[stt] Whisper ready.")
    return _model


def transcribe(audio_path: str, language: str | None = None) -> str:
    """
    Transcribe a WAV file. Returns the transcribed text.
    language: None = auto-detect, 'es' = Spanish, 'en' = English
    """
    model = _get_model()

    segments, info = model.transcribe(
        audio_path,
        language=language,        # None = auto-detect language per utterance
        beam_size=5,
        best_of=5,                # pick best of 5 candidates — better accuracy
        temperature=0.0,          # deterministic, no hallucination
        condition_on_previous_text=False,  # each utterance independent
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=200,
            speech_pad_ms=400,    # keep a bit more context around speech
        ),
    )

    text = " ".join(seg.text.strip() for seg in segments).strip()
    detected = info.language
    confidence = getattr(info, 'language_probability', '?')
    print(f"[stt] Language: {detected} ({confidence:.0%}) | '{text}'")
    return text


def preload_model() -> None:
    """Call this at startup to avoid first-use delay."""
    _get_model()
