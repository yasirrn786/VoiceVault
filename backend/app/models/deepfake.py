from __future__ import annotations

import logging
import threading
from time import perf_counter

import numpy as np

from app.config import settings
from app.services.audio import pcm16_bytes_to_float

logger = logging.getLogger(__name__)


class DeepfakeDetector:
    """Lazy adapter for a locally cached pretrained Wav2Vec2 deepfake classifier."""

    def __init__(self) -> None:
        self.model_name = settings.deepfake_model
        self.health = "STANDBY"
        self.device = "unresolved"
        self.error: str | None = None
        self._model = None
        self._processor = None
        self._torch = None
        self._lock = threading.RLock()

    def _resolve_device(self, torch: object) -> str:
        requested = settings.deepfake_device.strip().lower()
        if requested == "auto":
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        if requested.startswith("cuda") and not torch.cuda.is_available():
            logger.warning("Deepfake CUDA requested but unavailable; using CPU")
            return "cpu"
        return requested

    def _load(self) -> bool:
        if self._model is not None:
            return True
        with self._lock:
            if self._model is not None:
                return True
            try:
                import torch
                from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

                self.device = self._resolve_device(torch)
                self._processor = AutoFeatureExtractor.from_pretrained(self.model_name)
                self._model = AutoModelForAudioClassification.from_pretrained(self.model_name)
                self._model.to(self.device)
                self._model.eval()
                self._torch = torch
                self.health = "ONLINE"
                self.error = None
                logger.info("Deepfake model loaded: %s on %s", self.model_name, self.device)
                return True
            except Exception as exc:  # Model/download/device failures must not stop the API.
                self.error = f"{type(exc).__name__}: {exc}"
                self.health = "UNAVAILABLE"
                self._model = None
                logger.exception("Deepfake model unavailable: %s", self.error)
                return False

    def _fake_index(self) -> int | None:
        labels = getattr(self._model.config, "id2label", {}) if self._model is not None else {}
        for index, label in labels.items():
            if any(word in str(label).lower() for word in ("fake", "spoof", "synthetic", "deepfake")):
                return int(index)
        return None

    def analyze(self, audio: bytes, quality_good: bool = True) -> dict[str, object]:
        started = perf_counter()
        samples = pcm16_bytes_to_float(audio)
        if not quality_good or len(samples) < 16000:
            return {
                "synthetic_score": None,
                "confidence": 0.0,
                "label": "unknown",
                "status": "signal_degraded",
                "model": self.model_name,
                "latency_ms": round((perf_counter() - started) * 1000, 2),
            }
        if not self._load():
            return {
                "synthetic_score": None,
                "confidence": 0.0,
                "label": "unknown",
                "status": "unavailable",
                "model": self.model_name,
                "latency_ms": round((perf_counter() - started) * 1000, 2),
                "error": self.error,
            }
        try:
            # The checkpoint was trained at 16 kHz. A bounded window keeps demo latency stable.
            window = samples[: 16000 * 4]
            inputs = self._processor(
                window,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True,
            )
            inputs = {key: value.to(self.device) for key, value in inputs.items()}
            with self._lock, self._torch.inference_mode():
                logits = self._model(**inputs).logits[0]
                probabilities = self._torch.softmax(logits, dim=-1).detach().float().cpu().numpy()
            fake_index = self._fake_index()
            if fake_index is None or fake_index >= len(probabilities):
                raise RuntimeError("checkpoint label map has no synthetic/fake class")
            synthetic_score = float(probabilities[fake_index])
            confidence = float(np.max(probabilities))
            return {
                "synthetic_score": round(synthetic_score, 5),
                "confidence": round(confidence, 5),
                "label": "synthetic" if synthetic_score >= settings.deepfake_threshold else "genuine",
                "status": "ok",
                "model": self.model_name,
                "latency_ms": round((perf_counter() - started) * 1000, 2),
            }
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self.health = "DEGRADED"
            logger.exception("Deepfake inference failed: %s", self.error)
            return {
                "synthetic_score": None,
                "confidence": 0.0,
                "label": "unknown",
                "status": "unavailable",
                "model": self.model_name,
                "latency_ms": round((perf_counter() - started) * 1000, 2),
                "error": self.error,
            }


deepfake_detector = DeepfakeDetector()
