from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.enroll import router as enroll_router
from app.api.incidents import router as incidents_router
from app.api.live import router as live_router
from app.config import settings
from app.models.deepfake import deepfake_detector
from app.models.aasist import aasist_detector
from app.models.liveness import liveness_detector
from app.models.speaker import speaker_verifier
from app.services.gemini_context import context_engine
from app.services.transcription import transcriber

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="V.O.I.C.E. API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(live_router)
app.include_router(enroll_router)
app.include_router(incidents_router)


@app.on_event("startup")
async def report_runtime() -> None:
    try:
        import torch
        available = torch.cuda.is_available()
        name = torch.cuda.get_device_name(0) if available else "none"
        logger.info("CUDA available: %s | GPU name: %s", available, name)
    except Exception as exc:
        logger.info("CUDA available: False | GPU name: unavailable (%s)", exc)
    logger.info("Whisper device: %s", settings.whisper_device)
    logger.info("Deepfake model device: %s", settings.deepfake_device)
    logger.info("AASIST model device: %s", settings.aasist_device)
    logger.info("Speaker model device: %s", settings.speaker_device)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/model-health")
async def model_health() -> dict[str, object]:
    return {
        "Whisper": {"status": transcriber.health, "model": f"faster-whisper/{settings.whisper_model}", "device": transcriber.device},
        "Wav2Vec2": {"status": deepfake_detector.health, "model": deepfake_detector.model_name, "device": deepfake_detector.device, "error": deepfake_detector.error},
        "AASIST": {"status": aasist_detector.health, "model": aasist_detector.model_name, "checkpoint": aasist_detector.checkpoint_version, "device": aasist_detector.device, "error": aasist_detector.error},
        "ECAPA": {"status": speaker_verifier.health, "model": speaker_verifier.model_name, "device": speaker_verifier.device, "error": speaker_verifier.error},
        "Liveness": {"status": liveness_detector.health, "model": liveness_detector.model_name},
        "Gemini": {"status": context_engine.health},
    }


@app.get("/api/config")
async def public_config() -> dict[str, object]:
    return {"privacy_mode": not settings.raw_audio_retention, "raw_audio_retention": settings.raw_audio_retention, "speaker_threshold": settings.speaker_threshold}
