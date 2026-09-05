from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env", override=True)


@dataclass(frozen=True)
class Settings:
    app_name: str = "V.O.I.C.E."
    raw_audio_retention: bool = os.getenv("RAW_AUDIO_RETENTION", "false").lower() == "true"
    whisper_model: str = os.getenv("WHISPER_MODEL", "base.en")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    deepfake_model: str = os.getenv(
        "DEEPFAKE_MODEL", "garystafford/wav2vec2-deepfake-voice-detector"
    )
    deepfake_device: str = os.getenv("DEEPFAKE_DEVICE", "auto")
    deepfake_threshold: float = _float("DEEPFAKE_THRESHOLD", 0.50)
    aasist_checkpoint: str = os.getenv(
        "AASIST_CHECKPOINT", str(BASE_DIR / "data" / "models" / "aasist" / "AASIST.pth")
    )
    aasist_device: str = os.getenv("AASIST_DEVICE", "auto")
    speaker_model: str = os.getenv(
        "SPEAKER_MODEL", "speechbrain/spkrec-ecapa-voxceleb"
    )
    speaker_device: str = os.getenv("SPEAKER_DEVICE", "auto")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    speaker_threshold: float = _float("SPEAKER_SIMILARITY_THRESHOLD", 0.70)
    audio_window_seconds: float = _float("AUDIO_WINDOW_SECONDS", 3.0)
    audio_buffer_max_seconds: float = _float("AUDIO_BUFFER_MAX_SECONDS", 6.0)
    smoothing_alpha: float = _float("TRUST_SMOOTHING_ALPHA", 0.45)
    unknown_penalty: float = _float("UNKNOWN_SIGNAL_PENALTY", 0.12)
    high_value_inr: float = _float("HIGH_VALUE_INR", 100000)
    weights: dict[str, float] = field(default_factory=lambda: {
        "deepfake_risk": _float("WEIGHT_DEEPFAKE", 0.40),
        "identity_mismatch": _float("WEIGHT_IDENTITY", 0.25),
        "context_risk": _float("WEIGHT_CONTEXT", 0.20),
        "liveness_risk": _float("WEIGHT_LIVENESS", 0.10),
        "other_anomaly": _float("WEIGHT_ANOMALY", 0.05),
    })
    data_dir: Path = BASE_DIR / "data"


settings = Settings()
