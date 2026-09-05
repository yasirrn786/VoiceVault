from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class SecurityEvent(BaseModel):
    event: str
    timestamp: float = Field(ge=0)
    severity: Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    confidence: float = Field(ge=0, le=1)
    source: str
    session_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    previous_hash: str = ""
    event_hash: str = ""
