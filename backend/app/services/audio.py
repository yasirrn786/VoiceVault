from __future__ import annotations

import io
import wave
from dataclasses import dataclass

import numpy as np


@dataclass
class AudioQuality:
    status: str
    score: float
    rms: float
    clipping_ratio: float
    duration_seconds: float
    issues: list[str]


class RollingPcmBuffer:
    """Bounded, non-overlapping 16 kHz PCM windows for expensive inference."""

    def __init__(self, window_seconds: float = 3.0, max_seconds: float = 6.0, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self.window_bytes = int(window_seconds * sample_rate * 2)
        self.max_bytes = max(self.window_bytes, int(max_seconds * sample_rate * 2))
        self._buffer = bytearray()

    @property
    def seconds(self) -> float:
        return len(self._buffer) / (self.sample_rate * 2)

    def append(self, audio: bytes) -> None:
        usable = audio[: len(audio) - len(audio) % 2]
        self._buffer.extend(usable)
        if len(self._buffer) > self.max_bytes:
            del self._buffer[: len(self._buffer) - self.max_bytes]

    def take_window(self) -> bytes | None:
        if len(self._buffer) < self.window_bytes:
            return None
        window = bytes(self._buffer[: self.window_bytes])
        # Consume the window so almost identical audio is not repeatedly analysed.
        del self._buffer[: self.window_bytes]
        return window


def pcm16_bytes_to_float(audio: bytes) -> np.ndarray:
    if len(audio) < 2:
        return np.array([], dtype=np.float32)
    return np.frombuffer(audio[:len(audio) - len(audio) % 2], dtype="<i2").astype(np.float32) / 32768.0


def float_to_pcm16(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes()


def check_quality(samples: np.ndarray, sample_rate: int = 16000) -> AudioQuality:
    duration = len(samples) / sample_rate
    rms = float(np.sqrt(np.mean(samples ** 2))) if samples.size else 0.0
    clipping = float(np.mean(np.abs(samples) >= .99)) if samples.size else 0.0
    issues: list[str] = []
    if duration < .45:
        issues.append("very_short_chunk")
    if rms < .004:
        issues.append("silence" if rms < .001 else "low_rms")
    if clipping > .02:
        issues.append("clipping")
    score = max(0.0, 1 - (.35 if duration < .45 else 0) - (.55 if rms < .004 else 0) - min(.5, clipping * 5))
    return AudioQuality("poor" if issues else "good", round(score, 3), round(rms, 5), round(clipping, 5), round(duration, 3), issues)


def pcm_to_wav(audio: bytes, sample_rate: int = 16000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(audio)
    return output.getvalue()
