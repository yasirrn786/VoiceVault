from __future__ import annotations

import json
import logging
from fastapi import APIRouter, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from app.schemas.responses import ContextRequest
from app.services.audio import check_quality, pcm16_bytes_to_float
from app.services.session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analysis"])


@router.post("/api/analyze-context")
async def analyze_context_endpoint(request: ContextRequest):
    return await session_manager.analyze_text(request.transcript, request.session_id)


@router.post("/api/analyze-audio")
async def analyze_audio_endpoint(audio: UploadFile = File(...), session_id: str | None = Form(None), speaker_id: str | None = Form(None)):
    return await session_manager.analyze_audio(session_id or session_manager.create().state.session_id, await audio.read(), speaker_id)


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
                await websocket.send_json(update.model_dump(mode="json"))
            elif message.get("text"):
                data = json.loads(message["text"])
                if data.get("type") == "configure":
                    speaker_id = data.get("speaker_id")
                elif data.get("type") == "manual_transcript":
                    update = await session_manager.analyze_text(str(data.get("text", "")), runtime.state.session_id)
                    await websocket.send_json(update.model_dump(mode="json"))
                elif data.get("type") == "challenge":
                    phrase = session_manager.start_challenge(runtime.state.session_id)
                    await websocket.send_json({"type": "challenge_created", "phrase": phrase})
                elif data.get("type") == "stop":
                    runtime.state.status = "CLOSED"
                    await websocket.send_json({"type": "session_stopped", "session_id": runtime.state.session_id})
                    await websocket.close(); return
    except (WebSocketDisconnect, RuntimeError):
        runtime.state.status = "CLOSED"
    except Exception as exc:
        logger.exception("Live analysis failure")
        try: await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception: pass
