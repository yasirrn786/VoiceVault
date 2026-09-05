from __future__ import annotations

import asyncio
import json
import logging
from app.config import settings
from app.schemas.responses import ContextAnalysis
from app.services.context import analyze_context

logger = logging.getLogger(__name__)


class ContextEngine:
    def __init__(self) -> None:
        self.health = "NOT_CONFIGURED" if not settings.gemini_api_key else "STANDBY"

    async def analyze(self, transcript: str) -> ContextAnalysis:
        fallback = analyze_context(transcript)
        if not settings.gemini_api_key:
            return fallback
        try:
            from google import genai
            client = genai.Client(api_key=settings.gemini_api_key)
            prompt = (
                "Analyze this call transcript for social-engineering risk. Return only JSON with keys "
                "claimed_identity, urgency, secrecy, fear, financial_request, amount, currency, "
                "new_beneficiary, otp_request, credential_request, remote_access_request, action_type, "
                "authority_claim, bank_impersonation, context_risk. Transcript: " + transcript
            )
            response = await asyncio.to_thread(client.models.generate_content, model="gemini-2.5-flash-lite", contents=prompt)
            raw = (response.text or "{}").strip().removeprefix("```json").removesuffix("```").strip()
            data = json.loads(raw)
            merged = fallback.model_dump()
            for key in set(data) & set(merged):
                if key not in {"events", "source", "action_risk"} and data[key] is not None:
                    merged[key] = data[key]
            merged["source"] = "gemini+rules"
            self.health = "ONLINE"
            return ContextAnalysis.model_validate(merged)
        except Exception:
            self.health = "UNAVAILABLE"
            logger.exception("Gemini enhancement failed; using deterministic context rules")
            return fallback


context_engine = ContextEngine()
