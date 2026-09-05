from __future__ import annotations

import json
import logging
import threading
from time import perf_counter
from pathlib import Path

import numpy as np

from app.config import settings
from app.services.audio import pcm16_bytes_to_float

logger = logging.getLogger(__name__)


class _SpectralFallback:
    model_name = "spectral-embedding-fallback"

    @staticmethod
    def embedding(audio: bytes) -> np.ndarray | None:
        samples = pcm16_bytes_to_float(audio)
        if len(samples) < 16000:
            return None
        window = np.hanning(min(len(samples), 64000))
        spectrum = np.abs(np.fft.rfft(samples[: len(window)] * window))
        bands = np.array_split(np.log1p(spectrum), 64)
        vector = np.array([band.mean() for band in bands], dtype=np.float32)
        norm = np.linalg.norm(vector)
        return vector / norm if norm else None


class SpeakerVerifier:
    """SpeechBrain ECAPA-TDNN verifier with an explicit deterministic fallback."""

    def __init__(self) -> None:
        self.model_name = settings.speaker_model
        self.health = "STANDBY"
        self.device = "unresolved"
        self.error: str | None = None
        self._classifier = None
        self._torch = None
        self._lock = threading.RLock()
        self._fallback = _SpectralFallback()

    def _resolve_device(self, torch: object) -> str:
        requested = settings.speaker_device.strip().lower()
        if requested == "auto":
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        if requested.startswith("cuda") and not torch.cuda.is_available():
            logger.warning("Speaker CUDA requested but unavailable; using CPU")
            return "cpu"
        return requested

    def _load(self) -> bool:
        if self._classifier is not None:
            return True
        with self._lock:
            if self._classifier is not None:
                return True
            try:
                import torch
                from speechbrain.inference.speaker import EncoderClassifier
                from speechbrain.utils.fetching import LocalStrategy

                self.device = self._resolve_device(torch)
                savedir = settings.data_dir / "models" / "spkrec-ecapa-voxceleb"
                savedir.parent.mkdir(parents=True, exist_ok=True)
                self._classifier = EncoderClassifier.from_hparams(
                    source=self.model_name,
                    savedir=str(savedir),
                    run_opts={"device": self.device},
                    local_strategy=LocalStrategy.COPY,
                )
                self._torch = torch
                self.health = "READY"
                self.error = None
                logger.info("Speaker model loaded: %s on %s", self.model_name, self.device)
                return True
            except Exception as exc:
                self.error = f"{type(exc).__name__}: {exc}"
                self._classifier = None
                self.health = "DEGRADED"
                logger.exception("ECAPA unavailable; using spectral fallback: %s", self.error)
                return False

    def _ecapa_embedding(self, audio: bytes) -> np.ndarray | None:
        samples = pcm16_bytes_to_float(audio)
        if len(samples) < 16000:
            return None
        if not self._load():
            return None
        wav = self._torch.from_numpy(samples).float().unsqueeze(0).to(self.device)
        with self._lock, self._torch.inference_mode():
            embedding = self._classifier.encode_batch(wav).squeeze().detach().float().cpu().numpy()
        norm = np.linalg.norm(embedding)
        return embedding / norm if norm else None

    def _embedding(self, audio: bytes) -> tuple[np.ndarray | None, str]:
        try:
            embedding = self._ecapa_embedding(audio)
            if embedding is not None:
                return embedding, self.model_name
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self.health = "DEGRADED"
            logger.exception("ECAPA inference failed; using fallback: %s", self.error)
        return self._fallback.embedding(audio), self._fallback.model_name

    @staticmethod
    def _target(speaker_id: str) -> Path:
        safe_id = "".join(char for char in speaker_id if char.isalnum() or char in ("-", "_"))
        return settings.data_dir / "embeddings" / f"{safe_id}.json"

    def enroll(self, speaker_id: str, audio: bytes) -> dict[str, object]:
        started = perf_counter()
        embedding, model = self._embedding(audio)
        if embedding is None:
            return {"speaker_id": speaker_id, "embedding_status": "insufficient_audio", "model": model}
        target = self._target(speaker_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"model": model, "embedding": embedding.tolist()}), encoding="utf-8")
        return {"speaker_id": speaker_id, "embedding_status": "stored", "model": model, "health": self.health, "device": self.device, "latency_ms": round((perf_counter()-started)*1000, 2)}

    def verify(self, speaker_id: str | None, audio: bytes) -> dict[str, object]:
        started = perf_counter()
        if not speaker_id:
            return {"speaker_similarity": None, "speaker_match": "unknown", "model": self.model_name}
        target = self._target(speaker_id)
        embedding, model = self._embedding(audio)
        if not target.exists() or embedding is None:
            return {"speaker_similarity": None, "speaker_match": "unknown", "model": model}
        stored = json.loads(target.read_text(encoding="utf-8"))
        if stored.get("model") != model:
            return {"speaker_similarity": None, "speaker_match": "unknown", "model": model}
        enrolled = np.asarray(stored["embedding"], dtype=np.float32)
        denominator = float(np.linalg.norm(enrolled) * np.linalg.norm(embedding))
        if not denominator:
            return {"speaker_similarity": None, "speaker_match": "unknown", "model": model}
        similarity = float(np.dot(enrolled, embedding) / denominator)
        return {
            "claimed_speaker": speaker_id,
            "speaker_similarity": round(similarity, 4),
            "speaker_match": similarity >= settings.speaker_threshold,
            "threshold": settings.speaker_threshold,
            "model": model,
            "device": self.device,
            "latency_ms": round((perf_counter()-started)*1000, 2),
        }


speaker_verifier = SpeakerVerifier()
