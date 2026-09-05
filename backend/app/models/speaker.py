from __future__ import annotations

import json
import logging
from pathlib import Path
import numpy as np
from app.config import settings
from app.services.audio import pcm16_bytes_to_float

logger = logging.getLogger(__name__)


class SpeakerVerifier:
    """Lightweight, deterministic spectral embedding fallback with configurable threshold.

    It enables the enrollment workflow without claiming ECAPA-level accuracy. When a
    SpeechBrain adapter is added, this public interface remains unchanged.
    """

    model_name = "spectral-embedding-mvp"
    health = "DEGRADED"

    def _embedding(self, audio: bytes) -> np.ndarray | None:
        samples = pcm16_bytes_to_float(audio)
        if len(samples) < 16000:
            return None
        window = np.hanning(min(len(samples), 64000))
        spectrum = np.abs(np.fft.rfft(samples[:len(window)] * window))
        bands = np.array_split(np.log1p(spectrum), 64)
        vector = np.array([band.mean() for band in bands], dtype=np.float32)
        norm = np.linalg.norm(vector)
        return vector / norm if norm else None

    def enroll(self, speaker_id: str, audio: bytes) -> dict[str, object]:
        embedding = self._embedding(audio)
        if embedding is None:
            return {"speaker_id": speaker_id, "embedding_status": "insufficient_audio", "model": self.model_name}
        target = settings.data_dir / "embeddings" / f"{speaker_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"model": self.model_name, "embedding": embedding.tolist()}), encoding="utf-8")
        return {"speaker_id": speaker_id, "embedding_status": "stored", "model": self.model_name}

    def verify(self, speaker_id: str | None, audio: bytes) -> dict[str, object]:
        if not speaker_id:
            return {"speaker_similarity": None, "speaker_match": "unknown", "model": self.model_name}
        target = settings.data_dir / "embeddings" / f"{speaker_id}.json"
        embedding = self._embedding(audio)
        if not target.exists() or embedding is None:
            return {"speaker_similarity": None, "speaker_match": "unknown", "model": self.model_name}
        enrolled = np.asarray(json.loads(target.read_text(encoding="utf-8"))["embedding"], dtype=np.float32)
        similarity = float(np.dot(enrolled, embedding) / (np.linalg.norm(enrolled) * np.linalg.norm(embedding)))
        return {"speaker_similarity": round(similarity, 4), "speaker_match": similarity >= settings.speaker_threshold, "model": self.model_name}


speaker_verifier = SpeakerVerifier()
