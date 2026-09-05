from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from .event import SecurityEvent


class ContextRequest(BaseModel):
    transcript: str = Field(min_length=1)
    session_id: str | None = None


class ContextAnalysis(BaseModel):
    claimed_identity: str | None = None
    attack_type: str | None = None
    urgency: float = 0.0
    secrecy: float = 0.0
    fear: float = 0.0
    financial_request: bool = False
    amount: float | None = None
    currency: str | None = None
    new_beneficiary: bool = False
    otp_request: bool = False
    credential_request: bool = False
    remote_access_request: bool = False
    action_type: str | None = None
    authority_claim: bool = False
    bank_impersonation: bool = False
    context_risk: float = Field(ge=0, le=1)
    action_risk: float = Field(ge=0, le=1)
    source: str = "rules"
    events: list[dict[str, Any]] = Field(default_factory=list)


class AnalysisUpdate(BaseModel):
    type: str = "analysis_update"
    session_id: str
    timestamp: float
    transcript: dict[str, Any]
    context: ContextAnalysis
    signals: dict[str, Any]
    trust_score: float
    risk_score: float
    trust_band: str
    policy_decision: str
    policy_reasons: list[str]
    attack_chain: str | None = None
    events: list[SecurityEvent] = Field(default_factory=list)
    model_health: dict[str, str] = Field(default_factory=dict)
