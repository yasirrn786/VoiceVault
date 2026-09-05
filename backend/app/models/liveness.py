class LivenessDetector:
    model_name = "not-configured"
    health = "UNAVAILABLE"

    def analyze(self, _audio: bytes) -> dict[str, object]:
        return {"liveness_risk": None, "label": "unknown", "confidence": 0.0, "model": self.model_name}


liveness_detector = LivenessDetector()
