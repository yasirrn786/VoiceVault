from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from .event import SecurityEvent


class SessionStatus(str, Enum):
    NEW = "NEW"
    OBSERVING = "OBSERVING"
    VERIFIED = "VERIFIED"
    SUSPICIOUS = "SUSPICIOUS"
    CHALLENGED = "CHALLENGED"
    COMPROMISED = "COMPROMISED"
    CLOSED = "CLOSED"


class TranscriptEntry(BaseModel):
    timestamp: float
    text: str
    language: str = "en"
    confidence: float = 0.0


class SessionState(BaseModel):
    session_id: str
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: SessionStatus = SessionStatus.NEW
    claimed_identity: str | None = None
    verified_identity: str | None = None
    trust_score: float = 88.0
    risk_score: float = 0.12
    active_policy: str = "MONITOR"
    transcript: list[TranscriptEntry] = Field(default_factory=list)
    security_events: list[SecurityEvent] = Field(default_factory=list)
    attack_state: dict[str, Any] = Field(default_factory=dict)
    challenge_phrase: str | None = None
    challenge_status: str | None = None
    previous_event_hash: str = ""
