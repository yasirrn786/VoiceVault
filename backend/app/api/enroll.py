from __future__ import annotations
from fastapi import APIRouter, File, Form, UploadFile
from app.models.speaker import speaker_verifier

router = APIRouter(prefix="/api", tags=["speaker"])


@router.post("/enroll-speaker")
async def enroll_speaker(audio: UploadFile = File(...), speaker_id: str = Form(...)) -> dict[str, object]:
    payload = await audio.read()
    result = speaker_verifier.enroll(speaker_id, payload)
    result["raw_audio_retained"] = False
    return result
