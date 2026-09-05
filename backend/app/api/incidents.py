from fastapi import APIRouter, HTTPException
from app.services.incidents import create_incident, get_incident
from app.services.session_manager import session_manager

router = APIRouter(prefix="/api", tags=["incidents"])


@router.post("/incidents/{session_id}")
async def make_incident(session_id: str) -> dict[str, object]:
    runtime = session_manager.get(session_id)
    if runtime is None: raise HTTPException(404, "Session not found")
    return create_incident(runtime.state)


@router.get("/incidents/{session_id}")
async def read_incident(session_id: str) -> dict[str, object]:
    incident = get_incident(session_id)
    if incident is None: raise HTTPException(404, "Incident not found")
    return incident
