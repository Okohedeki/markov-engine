"""Audio transcription via faster-whisper. Pure (no Store).

The model is loaded lazily and cached process-wide; the CPU-bound transcription
runs in a thread executor so it never blocks the event loop.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TranscriptSegment:
    text: str
    start_seconds: float
    end_seconds: float
    speaker: str | None = None


_models: dict[str, object] = {}
_model_lock = asyncio.Lock()


def _get_model_sync(model_size: str):
    """Load the faster-whisper model (blocking). Called inside an executor."""
    from faster_whisper import WhisperModel

    logger.info(
        "Loading Whisper model '%s' (first-time download may take a moment)...",
        model_size,
    )
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    logger.info("Whisper model loaded")
    return model


async def _ensure_model(model_size: str):
    if model_size not in _models:
        async with _model_lock:
            if model_size not in _models:
                loop = asyncio.get_running_loop()
                _models[model_size] = await loop.run_in_executor(
                    None, _get_model_sync, model_size
                )
    return _models[model_size]


def _transcribe_sync(model, audio_path: str) -> list[TranscriptSegment]:
    """Run transcription and retain faster-whisper segment boundaries."""
    segments, info = model.transcribe(audio_path, beam_size=5)
    logger.info("Transcribing %.1fs of %s audio", info.duration, info.language)
    return [
        TranscriptSegment(
            text=segment.text.strip(),
            start_seconds=float(segment.start),
            end_seconds=float(segment.end),
        )
        for segment in segments
        if segment.text.strip()
    ]


async def transcribe_segments(
    audio_path: str, model_size: str = "base"
) -> list[TranscriptSegment]:
    """Transcribe audio into stable, timestamped segments."""
    model = await _ensure_model(model_size)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _transcribe_sync, model, audio_path)


async def transcribe(audio_path: str, model_size: str = "base") -> str:
    """Transcribe an audio file to text using faster-whisper.

    Runs the CPU-bound work in a thread executor to avoid blocking the event loop.
    """
    segments = await transcribe_segments(audio_path, model_size=model_size)
    return " ".join(segment.text for segment in segments)
