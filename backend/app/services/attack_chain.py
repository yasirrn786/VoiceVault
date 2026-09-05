from __future__ import annotations
from app.schemas.responses import ContextAnalysis


class AttackChainTracker:
    def __init__(self) -> None:
        self.flags: set[str] = set()

    def update(self, context: ContextAnalysis) -> str | None:
        if context.authority_claim: self.flags.add("AUTHORITY")
        if context.bank_impersonation: self.flags.add("BANK")
        if context.urgency > .5: self.flags.add("URGENCY")
        if context.secrecy > .5: self.flags.add("SECRECY")
        if context.fear > .5: self.flags.add("FEAR")
        if context.financial_request: self.flags.add("FINANCIAL")
        if context.otp_request: self.flags.add("OTP")
        if context.remote_access_request: self.flags.add("REMOTE")
        if context.new_beneficiary: self.flags.add("BENEFICIARY")
        event_names = {event.get("event") for event in context.events}
        if "FAMILY_CLAIM" in event_names: self.flags.add("FAMILY")
        if "EMERGENCY_CLAIM" in event_names: self.flags.add("EMERGENCY")
        if "TECH_SUPPORT_CLAIM" in event_names: self.flags.add("TECH_SUPPORT")
        if "DEVICE_ACCOUNT_PROBLEM" in event_names: self.flags.add("DEVICE_PROBLEM")

        if {"AUTHORITY", "URGENCY", "SECRECY", "FINANCIAL"} <= self.flags: return "CEO_FRAUD"
        if {"BANK", "OTP"} <= self.flags: return "OTP_HARVESTING"
        if {"FAMILY", "EMERGENCY", "URGENCY", "FINANCIAL"} <= self.flags: return "FAMILY_IMPERSONATION_FRAUD"
        if {"AUTHORITY", "FEAR", "SECRECY", "FINANCIAL"} <= self.flags: return "AUTHORITY_EXTORTION"
        if {"TECH_SUPPORT", "DEVICE_PROBLEM", "REMOTE"} <= self.flags: return "REMOTE_ACCESS_SCAM"
        if "REMOTE" in self.flags: return "REMOTE_ACCESS_SCAM"
        return None

    def snapshot(self) -> dict[str, object]:
        return {"observed_stages": sorted(self.flags)}
