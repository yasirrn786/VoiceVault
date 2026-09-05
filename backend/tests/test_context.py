import pytest
from app.services.context import analyze_context


@pytest.mark.parametrize(("text", "event"), [
    ("I am the CFO. Transfer ₹8 lakh to this new beneficiary immediately. This is confidential, don't contact finance.", "HIGH_VALUE_TRANSACTION"),
    ("I am calling from your bank. Your KYC will expire today. Tell me the OTP.", "OTP_REQUEST"),
    ("This is CBI. You are under investigation. Do not contact anybody. Transfer the verification amount now.", "THREAT_COERCION"),
    ("Install this app and share your screen so I can fix your bank account.", "REMOTE_ACCESS_REQUEST"),
    ("Read the six-digit security code sent to your phone immediately.", "OTP_REQUEST"),
])
def test_scam_scenarios(text: str, event: str) -> None:
    result = analyze_context(text)
    assert event in {item["event"] for item in result.events}
    assert result.context_risk >= .4


def test_normal_conversation_low_risk() -> None:
    result = analyze_context("Hello, are we still meeting for lunch tomorrow?")
    assert result.context_risk == 0
    assert result.events == []


def test_indian_amount_parsing() -> None:
    result = analyze_context("Transfer ₹8 lakh to the new beneficiary.")
    assert result.amount == 800000
    assert result.currency == "INR"
