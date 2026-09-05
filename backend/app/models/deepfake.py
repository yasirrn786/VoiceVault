from __future__ import annotations
from time import perf_counter


class DeepfakeDetector:
    """Swappable anti-spoof adapter. The MVP never invents probabilities."""

    model_name = "not-configured"
    health = "UNAVAILABLE"

    def analyze(self, _audio: bytes, quality_good: bool = True) -> dict[str, object]:
        started = perf_counter()
        return {
            "synthetic_score": None,
            "confidence": 0.0,
            "label": "unknown",
            "status": "unknown" if quality_good else "signal_degraded",
            "model": self.model_name,
            "latency_ms": round((perf_counter() - started) * 1000, 2),
        }


deepfake_detector = DeepfakeDetector()
