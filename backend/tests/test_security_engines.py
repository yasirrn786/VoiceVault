from app.schemas.event import SecurityEvent
from app.services.attack_chain import AttackChainTracker
from app.services.context import analyze_context
from app.services.incidents import hash_event, verify_chain
from app.services.policy import evaluate_policy
from app.services.trust import TrustEngine
from app.services.session_manager import SessionManager


def test_trust_fusion_smooths_and_declines() -> None:
    engine = TrustEngine(.08)
    normal = engine.calculate({"deepfake_risk": None, "identity_mismatch": None, "liveness_risk": None, "context_risk": 0, "other_anomaly": 0}, 0)
    risky = engine.calculate({"deepfake_risk": None, "identity_mismatch": None, "liveness_risk": None, "context_risk": .95, "other_anomaly": 0}, .9)
    later = engine.calculate({"deepfake_risk": None, "identity_mismatch": None, "liveness_risk": None, "context_risk": .95, "other_anomaly": 0}, .9)
    assert normal.trust_score > risky.trust_score > later.trust_score


def test_ceo_fraud_attack_chain_across_turns() -> None:
    tracker = AttackChainTracker()
    assert tracker.update(analyze_context("I am your CFO.")) is None
    assert tracker.update(analyze_context("Transfer ₹8 lakh to a new beneficiary immediately.")) is None
    assert tracker.update(analyze_context("Do not contact finance. This is confidential.")) == "CEO_FRAUD"


def test_high_value_policy_holds() -> None:
    context = analyze_context("Transfer ₹8 lakh to a new beneficiary immediately.")
    policy = evaluate_policy(48, context, "CEO_FRAUD")
    assert policy.decision == "HOLD TRANSACTION"


def test_hash_chain_detects_tampering() -> None:
    first = hash_event(SecurityEvent(event="A", timestamp=1, severity="LOW", confidence=.8, source="test", session_id="s"), "")
    second = hash_event(SecurityEvent(event="B", timestamp=2, severity="HIGH", confidence=.9, source="test", session_id="s"), first.event_hash)
    assert verify_chain([first, second])
    second.details["changed"] = True
    assert not verify_chain([first, second])


async def test_challenge_preserves_requested_action() -> None:
    manager = SessionManager()
    update = await manager.analyze_text("I am the CFO. Transfer ₹8 lakh to a new beneficiary immediately. This is confidential.")
    phrase = manager.start_challenge(update.session_id)
    await manager.analyze_text(phrase, update.session_id)
    state = manager.get(update.session_id).state
    assert state.attack_state["amount"] == 800000
    assert state.attack_state["requested_action"]["type"] == "bank_transfer"
