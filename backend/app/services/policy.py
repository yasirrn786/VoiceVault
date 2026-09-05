from __future__ import annotations
from dataclasses import dataclass
from app.config import settings
from app.schemas.responses import ContextAnalysis


@dataclass
class PolicyResult:
    decision: str
    reasons: list[str]


def evaluate_policy(trust: float, context: ContextAnalysis, attack_chain: str | None) -> PolicyResult:
    reasons: list[str] = []
    if trust < 25:
        return PolicyResult("BLOCK / ESCALATE", ["Trust is below the critical threshold"])
    if context.otp_request and context.bank_impersonation and context.urgency > .7:
        return PolicyResult("BLOCK / ESCALATE", ["Urgent OTP request from claimed bank identity"])
    if context.amount and context.amount > settings.high_value_inr and context.new_beneficiary and trust < 75:
        return PolicyResult("HOLD TRANSACTION", ["High-value transfer to a new beneficiary", "Require secondary MFA"])
    if attack_chain:
        reasons.append(f"Attack chain matched: {attack_chain}")
    if context.remote_access_request or context.credential_request:
        reasons.append("Sensitive access or credential action requested")
    if reasons or trust < 50:
        return PolicyResult("VERIFY CALLER", reasons or ["Trust requires independent verification"])
    if trust < 75 or context.action_risk >= .45:
        return PolicyResult("MONITOR", ["Elevated context or action risk"])
    return PolicyResult("ALLOW", ["No material threat condition met"])
