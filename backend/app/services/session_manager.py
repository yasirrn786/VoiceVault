from __future__ import annotations

import asyncio
import random
import time
import uuid
from dataclasses import dataclass, field

from app.config import settings
from app.models.deepfake import deepfake_detector
from app.models.liveness import liveness_detector
from app.models.speaker import speaker_verifier
from app.schemas.event import SecurityEvent
from app.schemas.responses import AnalysisUpdate, ContextAnalysis
from app.schemas.session import SessionState, SessionStatus, TranscriptEntry
from app.services.action_extractor import requested_action
from app.services.attack_chain import AttackChainTracker
from app.services.audio import RollingPcmBuffer, check_quality, pcm16_bytes_to_float
from app.services.gemini_context import context_engine
from app.services.incidents import hash_event
from app.services.policy import evaluate_policy
from app.services.transcription import transcriber
from app.services.trust import TrustEngine


@dataclass
class RuntimeSession:
    state: SessionState
    trust: TrustEngine
    chain: AttackChainTracker
    audio_buffer: RollingPcmBuffer = field(
        default_factory=lambda: RollingPcmBuffer(
            settings.audio_window_seconds, settings.audio_buffer_max_seconds
        )
    )


class SessionManager:
    def __init__(self) -> None:
        self.sessions: dict[str, RuntimeSession] = {}

    def create(self, session_id: str | None = None) -> RuntimeSession:
        sid = session_id or uuid.uuid4().hex[:12]
        runtime = RuntimeSession(
            SessionState(session_id=sid, status=SessionStatus.OBSERVING),
            TrustEngine(.12),
            AttackChainTracker(),
        )
        self.sessions[sid] = runtime
        return runtime

    def get(self, session_id: str) -> RuntimeSession | None:
        return self.sessions.get(session_id)

    def get_or_create(self, session_id: str | None = None) -> RuntimeSession:
        return self.sessions.get(session_id) if session_id and session_id in self.sessions else self.create(session_id)

    def start_challenge(self, session_id: str) -> str:
        runtime = self.get_or_create(session_id)
        phrase = f"{random.choice(['BLUE', 'AMBER', 'SILVER', 'GREEN'])} {random.randint(10, 99)} {random.choice(['RIVER', 'ORBIT', 'CLOUD', 'TIGER'])}"
        runtime.state.challenge_phrase = phrase
        runtime.state.challenge_status = "pending"
        runtime.state.status = SessionStatus.CHALLENGED
        return phrase

    async def analyze_audio(self, session_id: str, audio: bytes, speaker_id: str | None = None) -> AnalysisUpdate | None:
        """Accept chunks continuously, returning an update only for a fresh model window."""
        runtime = self.get_or_create(session_id)
        runtime.audio_buffer.append(audio)
        window = runtime.audio_buffer.take_window()
        if window is None:
            return None
        elapsed = max(0.0, time.time() - runtime.state.start_time.timestamp())
        samples = pcm16_bytes_to_float(window)
        quality = check_quality(samples)
        if quality.status == "poor":
            transcript = {"text": "", "language": "en", "confidence": 0.0, "status": "signal_degraded"}
            deepfake = deepfake_detector.analyze(window, quality_good=False)
            speaker = {"speaker_similarity": None, "speaker_match": "unknown", "model": speaker_verifier.model_name}
        else:
            transcription_task = asyncio.to_thread(transcriber.transcribe_pcm, window)
            deepfake_task = asyncio.to_thread(deepfake_detector.analyze, window, True)
            speaker_task = asyncio.to_thread(speaker_verifier.verify, speaker_id, window)
            transcript, deepfake, speaker = await asyncio.gather(
                transcription_task, deepfake_task, speaker_task
            )
        liveness = liveness_detector.analyze(window)
        return await self._analyze(
            runtime, str(transcript.get("text", "")), elapsed, quality, transcript,
            deepfake, speaker, liveness,
        )

    async def analyze_text(self, transcript: str, session_id: str | None = None) -> AnalysisUpdate:
        runtime = self.get_or_create(session_id)
        elapsed = max(0.0, time.time() - runtime.state.start_time.timestamp())
        transcription = {"text": transcript, "language": "en", "confidence": 1.0, "status": "manual"}
        unknown_deepfake = {
            "synthetic_score": None, "confidence": 0.0, "label": "unknown",
            "status": "unavailable", "model": deepfake_detector.model_name, "latency_ms": 0,
        }
        unknown_speaker = {"speaker_similarity": None, "speaker_match": "unknown", "model": speaker_verifier.model_name}
        return await self._analyze(runtime, transcript, elapsed, None, transcription, unknown_deepfake, unknown_speaker, liveness_detector.analyze(b""))

    async def _analyze(
        self, runtime: RuntimeSession, text: str, elapsed: float, quality, transcript: dict[str, object],
        deepfake: dict[str, object], speaker: dict[str, object], liveness: dict[str, object],
    ) -> AnalysisUpdate:
        context = await context_engine.analyze(text) if text else ContextAnalysis(context_risk=0, action_risk=0)
        if text:
            runtime.state.transcript.append(TranscriptEntry(timestamp=round(elapsed, 2), text=text, confidence=float(transcript.get("confidence", 0))))
        mismatch = None if speaker["speaker_match"] == "unknown" else (0.0 if speaker["speaker_match"] else 1.0)
        challenge_passed: bool | None = None
        if runtime.state.challenge_phrase and runtime.state.challenge_status == "pending" and text:
            expected = " ".join(runtime.state.challenge_phrase.lower().split())
            observed = " ".join(text.lower().split())
            challenge_passed = expected in observed
            runtime.state.challenge_status = "passed" if challenge_passed else "failed"
        anomaly = None if quality is None else (1 - quality.score)
        if challenge_passed is False:
            anomaly = 1.0
        elif challenge_passed is True and anomaly is None:
            anomaly = 0.0
        signals = {
            "deepfake_risk": deepfake["synthetic_score"],
            "identity_mismatch": mismatch,
            "liveness_risk": liveness["liveness_risk"],
            "context_risk": context.context_risk,
            "other_anomaly": anomaly,
        }
        result = runtime.trust.calculate(signals, context.action_risk)
        attack = runtime.chain.update(context)
        policy = evaluate_policy(result.trust_score, context, attack)
        runtime.state.trust_score = result.trust_score
        runtime.state.risk_score = result.risk_score
        runtime.state.active_policy = policy.decision
        runtime.state.claimed_identity = context.claimed_identity or runtime.state.claimed_identity
        runtime.state.status = SessionStatus.COMPROMISED if result.trust_score < 25 else SessionStatus.SUSPICIOUS if result.trust_score < 50 or attack else SessionStatus.OBSERVING
        runtime.state.attack_state.update(runtime.chain.snapshot())
        if attack:
            runtime.state.attack_state["classification"] = attack
        if context.action_type:
            runtime.state.attack_state["requested_action"] = requested_action(context)
        if context.amount is not None:
            runtime.state.attack_state["amount"] = context.amount
        runtime.state.attack_state["model_versions"] = {
            "whisper": settings_name(), "deepfake": deepfake["model"],
            "speaker": speaker["model"], "liveness": liveness["model"],
        }

        new_events: list[SecurityEvent] = []

        def append_event(event: SecurityEvent) -> None:
            hashed = hash_event(event, runtime.state.previous_event_hash)
            runtime.state.previous_event_hash = hashed.event_hash
            runtime.state.security_events.append(hashed)
            new_events.append(hashed)

        for raw in context.events:
            append_event(SecurityEvent(**raw, timestamp=round(elapsed, 2), session_id=runtime.state.session_id))
        if quality and quality.status == "poor":
            append_event(SecurityEvent(event="SIGNAL_DEGRADED", timestamp=round(elapsed, 2), severity="MEDIUM", confidence=1.0, source="audio_quality", session_id=runtime.state.session_id, details={"issues": quality.issues}))
        if deepfake.get("status") == "ok" and deepfake.get("label") == "synthetic":
            append_event(SecurityEvent(event="VOICE_SYNTHETIC", timestamp=round(elapsed, 2), severity="HIGH", confidence=float(deepfake.get("confidence", 0)), source="deepfake_model", session_id=runtime.state.session_id, details={"model": deepfake.get("model"), "synthetic_score": deepfake.get("synthetic_score")}))
        elif deepfake.get("status") == "unavailable":
            append_event(SecurityEvent(event="MODEL_UNCERTAIN", timestamp=round(elapsed, 2), severity="LOW", confidence=0.0, source="deepfake_model", session_id=runtime.state.session_id, details={"model": deepfake.get("model"), "reason": "model_unavailable"}))
        if speaker.get("speaker_match") is False:
            append_event(SecurityEvent(event="SPEAKER_MISMATCH", timestamp=round(elapsed, 2), severity="HIGH", confidence=abs(float(speaker.get("speaker_similarity") or 0.0)), source="speaker_verifier", session_id=runtime.state.session_id, details={"model": speaker.get("model"), "similarity": speaker.get("speaker_similarity")}))
        if challenge_passed is not None:
            append_event(SecurityEvent(event="CHALLENGE_PASSED" if challenge_passed else "CHALLENGE_FAILED", timestamp=round(elapsed, 2), severity="INFO" if challenge_passed else "HIGH", confidence=float(transcript.get("confidence", 0)), source="active_challenge", session_id=runtime.state.session_id))

        public_signals = {
            "synthetic_voice_risk": deepfake, "speaker": speaker, "liveness": liveness,
            "audio_quality": None if quality is None else quality.__dict__,
            "context_risk": context.context_risk, "action_risk": context.action_risk,
        }
        return AnalysisUpdate(session_id=runtime.state.session_id, timestamp=round(elapsed, 2), transcript=transcript, context=context,
            signals=public_signals, trust_score=result.trust_score, risk_score=result.risk_score, trust_band=result.band,
            policy_decision=policy.decision, policy_reasons=policy.reasons, attack_chain=attack, events=new_events,
            model_health={"Whisper": transcriber.health, "Deepfake": deepfake_detector.health, "Speaker": speaker_verifier.health, "Liveness": liveness_detector.health, "Gemini": context_engine.health})


def settings_name() -> str:
    return f"faster-whisper/{settings.whisper_model}"


session_manager = SessionManager()
