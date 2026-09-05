from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.enroll import router as enroll_router
from app.api.incidents import router as incidents_router
from app.api.live import router as live_router
from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="V.O.I.C.E. API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(live_router); app.include_router(enroll_router); app.include_router(incidents_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/api/config")
async def public_config() -> dict[str, object]:
    return {"privacy_mode": not settings.raw_audio_retention, "raw_audio_retention": settings.raw_audio_retention, "speaker_threshold": settings.speaker_threshold}
