from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from app.config import settings
from app.schemas.event import SecurityEvent
from app.schemas.session import SessionState


def hash_event(event: SecurityEvent, previous_hash: str) -> SecurityEvent:
    payload = event.model_dump(exclude={"event_hash", "previous_hash"}, mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    event.previous_hash = previous_hash
    event.event_hash = hashlib.sha256((previous_hash + canonical).encode("utf-8")).hexdigest()
    return event


def verify_chain(events: list[SecurityEvent]) -> bool:
    previous = ""
    for item in events:
        copy = item.model_copy()
        expected = hash_event(copy, previous).event_hash
        if item.previous_hash != previous or item.event_hash != expected: return False
        previous = item.event_hash
    return True


def create_incident(session: SessionState) -> dict[str, object]:
    incident = {
        "incident_id": f"INC-{uuid.uuid4().hex[:10].upper()}",
        "session_id": session.session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "claimed_identity": session.claimed_identity,
        "final_trust": session.trust_score,
        "security_events": [event.model_dump(mode="json") for event in session.security_events],
        "attack_chain_classification": session.attack_state.get("classification"),
        "requested_action": session.attack_state.get("requested_action"),
        "amount": session.attack_state.get("amount"),
        "policy_triggered": session.active_policy,
        "recommended_response": session.active_policy,
        "model_versions": session.attack_state.get("model_versions", {}),
        "hash_chain_valid": verify_chain(session.security_events),
    }
    folder = settings.data_dir / "incidents"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{session.session_id}.json").write_text(json.dumps(incident, indent=2, ensure_ascii=False), encoding="utf-8")
    return incident


def get_incident(session_id: str) -> dict[str, object] | None:
    path = settings.data_dir / "incidents" / f"{session_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
