from __future__ import annotations

import logging
import threading
from pathlib import Path
from time import perf_counter

import numpy as np

from app.config import BASE_DIR, settings
from app.services.audio import pcm16_bytes_to_float

logger = logging.getLogger(__name__)


class AASISTDetector:
    """Official clovaai/AASIST architecture and ASVspoof2019-LA checkpoint adapter."""

    model_name = "clovaai/AASIST"
    checkpoint_version = "official-main/AASIST.pth"
    checkpoint_sha256 = "51d2d9cf0738172f61e2a384ec50a54a55363240f67c971ed55a92435bc1a1c0"

    def __init__(self) -> None:
        self.health = "STANDBY"
        self.device = "unresolved"
        self.error: str | None = None
        self._model = None
        self._torch = None
        self._lock = threading.RLock()

    def _load(self) -> bool:
        if self._model is not None:
            return True
        with self._lock:
            if self._model is not None:
                return True
            try:
                import torch
                from app.models.aasist_architecture import Model

                requested = settings.aasist_device.lower()
                self.device = "cuda:0" if requested == "auto" and torch.cuda.is_available() else "cpu" if requested == "auto" else requested
                checkpoint = Path(settings.aasist_checkpoint)
                if not checkpoint.is_absolute():
                    checkpoint = BASE_DIR.parent / checkpoint
                if not checkpoint.is_file():
                    raise FileNotFoundError(f"official checkpoint not found: {checkpoint}")
                config = {
                    "filts": [70, [1, 32], [32, 32], [32, 64], [64, 64]],
                    "first_conv": 128,
                    "gat_dims": [64, 32],
                    "pool_ratios": [0.5, 0.7, 0.5, 0.5],
                    "temperatures": [2.0, 2.0, 100.0, 100.0],
                }
                model = Model(config)
                state = torch.load(checkpoint, map_location="cpu", weights_only=True)
                model.load_state_dict(state, strict=True)
                model.to(self.device).eval()
                self._model, self._torch = model, torch
                self.health, self.error = "READY", None
                return True
            except Exception as exc:
                self.health = "UNAVAILABLE"
                self.error = f"{type(exc).__name__}: {exc}"
                logger.exception("AASIST unavailable")
                return False

    @staticmethod
    def _reference_pad(samples: np.ndarray, length: int = 64600) -> np.ndarray:
        if not len(samples):
            return samples
        if len(samples) >= length:
            return samples[:length]
        return np.tile(samples, int(length / len(samples)) + 1)[:length]

    def analyze(self, audio: bytes, quality_good: bool = True) -> dict[str, object]:
        started = perf_counter()
        samples = pcm16_bytes_to_float(audio)
        base = {"model": self.model_name, "checkpoint": self.checkpoint_version, "device": self.device}
        if not quality_good or len(samples) < 16000:
            return {**base, "raw_score": None, "synthetic_score": None, "confidence": 0.0, "label": "unknown", "status": "signal_degraded", "latency_ms": round((perf_counter()-started)*1000, 2)}
        if not self._load():
            return {**base, "device": self.device, "raw_score": None, "synthetic_score": None, "confidence": 0.0, "label": "unknown", "status": "unavailable", "error": self.error, "latency_ms": round((perf_counter()-started)*1000, 2)}
        try:
            waveform = self._torch.from_numpy(self._reference_pad(samples)).float().unsqueeze(0).to(self.device)
            with self._lock, self._torch.inference_mode():
                _, logits = self._model(waveform, Freq_aug=False)
                probs = self._torch.softmax(logits[0], dim=-1).detach().float().cpu().numpy()
            # Official labels are spoof=0, bonafide=1. Softmax is a display-normalized
            # model score, not a calibrated probability.
            spoof_score = float(probs[0])
            return {**base, "device": self.device, "raw_score": round(float(logits[0, 1].item()), 6), "synthetic_score": round(spoof_score, 6), "confidence": round(float(max(probs)), 6), "label": "synthetic" if spoof_score >= .5 else "genuine", "status": "ok", "normalization": "softmax(spoof_logit)", "latency_ms": round((perf_counter()-started)*1000, 2)}
        except Exception as exc:
            self.health, self.error = "ERROR", f"{type(exc).__name__}: {exc}"
            return {**base, "raw_score": None, "synthetic_score": None, "confidence": 0.0, "label": "unknown", "status": "error", "error": self.error, "latency_ms": round((perf_counter()-started)*1000, 2)}


aasist_detector = AASISTDetector()
