from __future__ import annotations

import logging
import os
import tempfile
from threading import Lock
from app.config import settings
from app.services.audio import pcm_to_wav

logger = logging.getLogger(__name__)


class Transcriber:
    def __init__(self) -> None:
        self.model = None
        self.error: str | None = None
        self._lock = Lock()

    @property
    def health(self) -> str:
        return "ONLINE" if self.model is not None else "DEGRADED" if self.error else "STANDBY"

    def _load(self) -> None:
        if self.model is not None or self.error:
            return
        with self._lock:
            if self.model is not None or self.error:
                return
            try:
                from faster_whisper import WhisperModel
                self.model = WhisperModel(settings.whisper_model, device=settings.whisper_device, compute_type=settings.whisper_compute_type)
                logger.info("Loaded faster-whisper model %s", settings.whisper_model)
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                logger.exception("faster-whisper unavailable")

    def transcribe_pcm(self, audio: bytes) -> dict[str, object]:
        self._load()
        if self.model is None:
            return {"text": "", "language": "en", "confidence": 0.0, "status": "unavailable"}
        path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                handle.write(pcm_to_wav(audio)); path = handle.name
            segments, info = self.model.transcribe(path, language="en", vad_filter=True, beam_size=1)
            items = list(segments)
            text = " ".join(item.text.strip() for item in items).strip()
            avg_logprob = sum(item.avg_logprob for item in items) / len(items) if items else -5.0
            confidence = max(0.0, min(1.0, 1.0 + avg_logprob / 5.0))
            return {"text": text, "language": info.language or "en", "confidence": round(confidence, 3), "status": "ok"}
        except Exception:
            logger.exception("Transcription failed")
            return {"text": "", "language": "en", "confidence": 0.0, "status": "error"}
        finally:
            if path:
                try: os.unlink(path)
                except OSError: pass


transcriber = Transcriber()
