from __future__ import annotations
from dataclasses import dataclass
from app.config import settings


@dataclass
class TrustResult:
    risk_score: float
    trust_score: float
    band: str


class TrustEngine:
    def __init__(self, initial_risk: float | None = None) -> None:
        self.smoothed_risk = initial_risk

    def calculate(self, signals: dict[str, float | None], action_risk: float = 0.0) -> TrustResult:
        weighted = 0.0
        available_weight = 0.0
        missing_weight = 0.0
        for name, weight in settings.weights.items():
            value = signals.get(name)
            if value is None:
                missing_weight += weight
            else:
                weighted += max(0.0, min(1.0, value)) * weight
                available_weight += weight
        evidence_risk = weighted / available_weight if available_weight else 0.0
        current = min(1.0, evidence_risk + missing_weight * settings.unknown_penalty + action_risk * .18)
        self.smoothed_risk = current if self.smoothed_risk is None else settings.smoothing_alpha * current + (1 - settings.smoothing_alpha) * self.smoothed_risk
        risk = round(max(0.0, min(1.0, self.smoothed_risk)), 4)
        trust = round(100 * (1 - risk), 1)
        band = "TRUSTED" if trust >= 75 else "MONITOR" if trust >= 50 else "VERIFY" if trust >= 25 else "CRITICAL"
        return TrustResult(risk, trust, band)
