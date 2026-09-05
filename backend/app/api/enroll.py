from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from app.config import settings
from app.models.speaker import speaker_verifier

router = APIRouter(prefix="/api", tags=["speaker"])


@router.get("/speakers")
async def list_speakers() -> dict[str, object]:
    directory = settings.data_dir / "embeddings"
    ids = sorted(path.stem for path in directory.glob("*.json")) if directory.exists() else []
    return {"speakers": ids}


@router.post("/enroll-speaker")
async def enroll_speaker(audio: UploadFile = File(...), speaker_id: str = Form(...)) -> dict[str, object]:
    payload = await audio.read()
    result = await asyncio.to_thread(speaker_verifier.enroll, speaker_id, payload)
    result["raw_audio_retained"] = False
    return result
