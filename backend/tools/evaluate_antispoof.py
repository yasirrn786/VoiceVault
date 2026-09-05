"""Evaluate VoiceVault anti-spoof adapters from a CSV: audio_path,label.

Labels must be `bonafide` or `spoof`. This script never downloads datasets.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio.functional as AF

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models.aasist import aasist_detector
from app.models.antispoof_ensemble import fuse_antispoof
from app.models.deepfake import deepfake_detector
from app.services.audio import float_to_pcm16


def load_pcm(path: Path) -> bytes:
    samples, rate = sf.read(path, dtype="float32", always_2d=True)
    mono = samples.mean(1)
    if rate != 16000:
        mono = AF.resample(torch.from_numpy(mono), rate, 16000).numpy()
    return float_to_pcm16(mono)


def metrics(labels: list[int], scores: list[float], threshold: float = .5) -> dict[str, object]:
    y, s = np.asarray(labels), np.asarray(scores)
    pred = (s >= threshold).astype(int)
    tp, tn = int(((pred == 1) & (y == 1)).sum()), int(((pred == 0) & (y == 0)).sum())
    fp, fn = int(((pred == 1) & (y == 0)).sum()), int(((pred == 0) & (y == 1)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    result: dict[str, object] = {"samples": len(y), "confusion_matrix": [[tn, fp], [fn, tp]], "precision": precision, "recall": recall, "f1": f1}
    if len(set(labels)) == 2:
        thresholds = np.unique(s)
        fars, frrs = [], []
        for value in thresholds:
            p = s >= value
            fars.append(float(((p == 1) & (y == 0)).sum() / (y == 0).sum()))
            frrs.append(float(((p == 0) & (y == 1)).sum() / (y == 1).sum()))
        index = int(np.argmin(np.abs(np.asarray(fars) - np.asarray(frrs))))
        result["eer"] = (fars[index] + frrs[index]) / 2
        result["roc_auc"] = float(np.mean([np.mean(s[y == 1] > value) + .5 * np.mean(s[y == 1] == value) for value in s[y == 0]]))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--model", choices=["wav2vec2", "aasist", "ensemble"], required=True)
    args = parser.parse_args()
    labels, scores, latencies = [], [], []
    with args.manifest.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["label"] not in {"bonafide", "spoof"}: raise ValueError(f"invalid label: {row['label']}")
            pcm = load_pcm(Path(row["audio_path"]))
            wav = deepfake_detector.analyze(pcm) if args.model in {"wav2vec2", "ensemble"} else {}
            aas = aasist_detector.analyze(pcm) if args.model in {"aasist", "ensemble"} else {}
            result = wav if args.model == "wav2vec2" else aas if args.model == "aasist" else fuse_antispoof(wav, aas)
            score = result.get("synthetic_score")
            if score is None: raise RuntimeError(f"{args.model} unavailable: {result.get('error', result.get('status'))}")
            labels.append(1 if row["label"] == "spoof" else 0); scores.append(float(score))
            latency = float(result.get("latency_ms", 0))
            if args.model == "ensemble": latency = float(wav.get("latency_ms", 0)) + float(aas.get("latency_ms", 0))
            latencies.append(latency)
    output = metrics(labels, scores)
    output["model"] = args.model; output["average_inference_latency_ms"] = sum(latencies) / len(latencies)
    print(json.dumps(output, indent=2))


if __name__ == "__main__": main()
