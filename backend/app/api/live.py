from __future__ import annotations

import asyncio
import io
import json
import logging

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

from app.models.deepfake import deepfake_detector
from app.schemas.responses import ContextRequest
from app.services.audio import check_quality, float_to_pcm16
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analysis"])


@router.post("/api/analyze-context")
async def analyze_context_endpoint(request: ContextRequest):
    return await session_manager.analyze_text(request.transcript, request.session_id)


@router.post("/api/analyze-audio")
async def analyze_audio_endpoint(audio: UploadFile = File(...), session_id: str | None = Form(None), speaker_id: str | None = Form(None)):
    update = await session_manager.analyze_audio(session_id or session_manager.create().state.session_id, await audio.read(), speaker_id)
    return update.model_dump(mode="json") if update else {"status": "buffering", "required_seconds": 3}


@router.post("/api/debug/deepfake")
async def deepfake_debug_endpoint(audio: UploadFile = File(...)):
    """Developer/demo endpoint: executes the actual classifier; it does not report accuracy."""
    payload = await audio.read()
    if not payload:
        raise HTTPException(status_code=422, detail="Audio upload is empty")
    try:
        import soundfile as sf
        samples, sample_rate = sf.read(io.BytesIO(payload), dtype="float32", always_2d=True)
        mono = np.asarray(samples.mean(axis=1), dtype=np.float32)
        if sample_rate != 16000:
            import torch
            import torchaudio.functional as functional
            mono = functional.resample(torch.from_numpy(mono), sample_rate, 16000).numpy()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not decode {audio.filename or 'audio'}: {exc}") from exc
    quality = check_quality(mono)
    result = await asyncio.to_thread(deepfake_detector.analyze, float_to_pcm16(mono), quality.status == "good")
    return {"audio_quality": quality.__dict__, **result}


@router.websocket("/ws/live-analysis")
async def live_analysis(websocket: WebSocket) -> None:
    await websocket.accept()
    requested_session = websocket.query_params.get("session_id")
    runtime = session_manager.get_or_create(requested_session)
    speaker_id: str | None = None
    await websocket.send_json({"type": "session_started", "session_id": runtime.state.session_id, "privacy_mode": True})
    try:
        while True:
            message = await websocket.receive()
            if message.get("bytes") is not None:
                update = await session_manager.analyze_audio(runtime.state.session_id, message["bytes"], speaker_id)
                if update is not None:
                    await websocket.send_json(update.model_dump(mode="json"))
            elif message.get("text"):
                data = json.loads(message["text"])
                if data.get("type") == "configure":
                    speaker_id = data.get("speaker_id")
                    await websocket.send_json({"type": "configured", "speaker_id": speaker_id})
                elif data.get("type") == "manual_transcript":
                    update = await session_manager.analyze_text(str(data.get("text", "")), runtime.state.session_id)
                    await websocket.send_json(update.model_dump(mode="json"))
                elif data.get("type") == "challenge":
                    phrase = session_manager.start_challenge(runtime.state.session_id)
                    await websocket.send_json({"type": "challenge_created", "phrase": phrase})
                elif data.get("type") == "stop":
                    runtime.state.status = "CLOSED"
                    await websocket.send_json({"type": "session_stopped", "session_id": runtime.state.session_id})
                    await websocket.close()
                    return
    except (WebSocketDisconnect, RuntimeError):
        runtime.state.status = "CLOSED"
    except Exception as exc:
        logger.exception("Live analysis failure")
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
