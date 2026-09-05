from __future__ import annotations

import re
from typing import Iterable
from app.schemas.responses import ContextAnalysis


PATTERNS: dict[str, tuple[str, ...]] = {
    "urgency": (r"\burgent(?:ly)?\b", r"\bimmediately\b", r"\bright now\b", r"\btoday\b", r"\bexpire[sd]?\b", r"\basap\b"),
    "secrecy": (r"\bconfidential\b", r"don'?t (?:tell|contact|inform)", r"\bdo not (?:tell|contact|inform)\b", r"\bkeep (?:it|this) secret\b", r"\bno one else\b"),
    "fear": (r"\barrest(?:ed)?\b", r"\binvestigation\b", r"\blegal action\b", r"\baccount (?:will be )?(?:blocked|frozen)\b", r"\bpenalty\b", r"\bthreat\b"),
    "financial": (r"\btransfer\b", r"\bsend (?:money|funds|payment)\b", r"\bpay(?:ment)?\b", r"\bupi\b", r"\bbeneficiary\b", r"\bverification amount\b"),
    "otp": (r"\botp\b", r"one[- ]time pass(?:word|code)", r"verification code"),
    "credential": (r"\bpassword\b", r"\bpin\b", r"\bcvv\b", r"login details", r"credentials?"),
    "remote": (r"\bscreen share\b", r"\bshare (?:your )?screen\b", r"\bremote access\b", r"\binstall (?:this |the )?(?:app|application|anydesk|teamviewer)\b"),
    "beneficiary": (r"\bnew beneficiary\b", r"\badd (?:a )?beneficiary\b", r"\bnew account\b"),
    "authority": (r"\bcfo\b", r"\bceo\b", r"\bdirector\b", r"\bmanager\b", r"\bpolice\b", r"\bcbi\b", r"\bgovernment\b", r"\bofficer\b"),
    "bank": (r"\b(?:from|calling from|representing) (?:your |the )?bank\b", r"\b(?:your|the) bank\b", r"\bbank (?:agent|officer|team)\b", r"\bkyc\b"),
    "kyc": (r"\bkyc\b", r"know your customer"),
}


def _hit(text: str, names: Iterable[str]) -> bool:
    return any(re.search(pattern, text, re.I) for name in names for pattern in PATTERNS[name])


def _amount(text: str) -> tuple[float | None, str | None]:
    number = r"[\d,.]+|one|two|three|four|five|six|seven|eight|nine|ten"
    match = re.search(rf"\b({number})\s*(lakh|lac|crore|thousand|k)\b", text, re.I)
    if not match:
        match = re.search(rf"(?:₹|\brs\.?\b|\binr\b)\s*({number})", text, re.I)
    if not match:
        return None, None
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    raw = match.group(1).lower().replace(",", "")
    try:
        value = float(words.get(raw, raw))
    except ValueError:
        return None, None
    multiplier = {"lakh": 100000, "lac": 100000, "crore": 10000000, "thousand": 1000, "k": 1000}.get((match.group(2) or "").lower(), 1)
    amount = value * multiplier
    if amount < 100 and not match.group(2) and not re.search(r"₹|\brs\.?\b|\binr\b", text, re.I):
        return None, None
    return amount, "INR" if re.search(r"₹|\brs\.?\b|\binr\b|lakh|lac|crore", text, re.I) else None


def analyze_context(transcript: str) -> ContextAnalysis:
    text = transcript.strip()
    urgency = 0.92 if _hit(text, ["urgency"]) else 0.0
    secrecy = 0.93 if _hit(text, ["secrecy"]) else 0.0
    fear = 0.94 if _hit(text, ["fear"]) else 0.0
    financial = _hit(text, ["financial"])
    otp = _hit(text, ["otp"])
    credential = _hit(text, ["credential"])
    remote = _hit(text, ["remote"])
    beneficiary = _hit(text, ["beneficiary"])
    authority = _hit(text, ["authority"])
    bank = _hit(text, ["bank"])
    kyc = _hit(text, ["kyc"])
    amount, currency = _amount(text)

    identity = None
    for label, pattern in (("CFO", r"\bcfo\b"), ("CEO", r"\bceo\b"), ("CBI", r"\bcbi\b"), ("POLICE", r"\bpolice\b"), ("BANK", r"\bbank\b"), ("GOVERNMENT", r"\bgovernment\b")):
        if re.search(pattern, text, re.I):
            identity = label
            break

    action_type = "remote_access" if remote else "credential_submission" if credential or otp else "bank_transfer" if financial else None
    components = [urgency * .17, secrecy * .16, fear * .16, .24 if financial else 0, .28 if otp or credential else 0, .50 if remote else 0, .14 if authority or bank else 0, .12 if beneficiary else 0]
    context_risk = min(1.0, sum(components))
    action_risk = min(1.0, (.45 if financial else 0) + (.55 if otp or credential else 0) + (.55 if remote else 0) + (.20 if beneficiary else 0) + (.18 if amount and amount >= 100000 else 0))

    events: list[dict[str, object]] = []
    def add(event: str, severity: str, confidence: float) -> None:
        events.append({"event": event, "severity": severity, "confidence": confidence, "source": "context_engine"})
    if authority or bank: add("AUTHORITY_CLAIM", "MEDIUM", .88)
    if kyc: add("KYC_PRETEXT", "HIGH", .90)
    if urgency: add("URGENCY_DETECTED", "HIGH", urgency)
    if secrecy: add("SECRECY_REQUEST", "HIGH", secrecy)
    if fear: add("THREAT_COERCION", "HIGH", fear)
    if otp: add("OTP_REQUEST", "CRITICAL", .98)
    if credential: add("CREDENTIAL_REQUEST", "CRITICAL", .96)
    if financial: add("FINANCIAL_REQUEST", "HIGH", .94)
    if beneficiary: add("NEW_BENEFICIARY", "HIGH", .93)
    if amount and amount >= 100000: add("HIGH_VALUE_TRANSACTION", "CRITICAL", .95)
    if remote: add("REMOTE_ACCESS_REQUEST", "CRITICAL", .97)

    return ContextAnalysis(claimed_identity=identity, urgency=urgency, secrecy=secrecy, fear=fear,
        financial_request=financial, amount=amount, currency=currency, new_beneficiary=beneficiary,
        otp_request=otp, credential_request=credential, remote_access_request=remote,
        action_type=action_type, authority_claim=authority, bank_impersonation=bank,
        context_risk=round(context_risk, 3), action_risk=round(action_risk, 3), events=events)
