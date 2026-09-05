from __future__ import annotations


def fuse_antispoof(wav2vec2: dict[str, object], aasist: dict[str, object]) -> dict[str, object]:
    available = [item for item in (wav2vec2, aasist) if item.get("status") == "ok" and item.get("synthetic_score") is not None]
    if not available:
        return {"synthetic_score": None, "classification": "unknown", "confidence": 0.0, "status": "unavailable", "strategy": "conservative-unweighted-evidence"}
    if len(available) == 1:
        score = float(available[0]["synthetic_score"])
        return {"synthetic_score": score, "classification": available[0]["label"], "confidence": float(available[0].get("confidence", 0)), "status": "degraded", "strategy": "single-available-model; uncalibrated"}
    scores = [float(item["synthetic_score"]) for item in available]
    labels = [str(item["label"]) for item in available]
    if len(set(labels)) > 1 or abs(scores[0] - scores[1]) >= .45:
        return {"synthetic_score": round(sum(scores)/2, 6), "classification": "disagreement", "confidence": 1-round(abs(scores[0]-scores[1]), 6), "status": "verify", "strategy": "explicit-disagreement; uncalibrated"}
    score = max(scores) if labels[0] == "synthetic" else sum(scores)/2
    return {"synthetic_score": round(score, 6), "classification": labels[0], "confidence": round(min(float(item.get("confidence", 0)) for item in available), 6), "status": "ok", "strategy": "conservative-consensus; uncalibrated"}
