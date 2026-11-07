import re
from enum import Enum
from typing import Optional, Any

class EmergencyKind(str, Enum):
    MEDICAL = "medical"
    SELF_HARM = "self_harm"

_SELF_HARM = re.compile(
    r"\b(suicid\w*|kill(?:ing)? myself|end(?:ing)? my (?:own )?life|want(?:ed)? to die|self[- ]?harm|hurt(?:ing)? myself)\b",
    re.I,
)
_RISK_QUESTION_EXCLUSION = re.compile(
    r"\b(risk\s+of|chance\s+of|prevent\w*|family\s+history\s+of|what\s+is\s+a|does\s+my\s+.*?\s+raise|can\s+high\s+.*?\s+cause)\b",
    re.I,
)
_MEDICAL = re.compile(
    r"\b(chest (?:pain|tightness|pressure)|can'?t breathe|cannot breathe|can not breathe|"
    r"(?:trouble|difficulty|shortness of) breath\w*|severe bleeding|coughing (?:up )?blood|"
    r"unconscious|unresponsive|seizure|overdos\w*|anaphyla\w*|"
    r"(?:having|had|think i'?m having|experiencing) a (?:heart attack|stroke))\b",
    re.I,
)
_ACUTE_UNQUALIFIED = re.compile(r"\b(heart attack|stroke)\b", re.I)

def detect_emergency(query: str) -> Optional[EmergencyKind]:
    if not query:
        return None
    if _SELF_HARM.search(query):
        return EmergencyKind.SELF_HARM
    if _MEDICAL.search(query):
        return EmergencyKind.MEDICAL
    if _ACUTE_UNQUALIFIED.search(query) and not _RISK_QUESTION_EXCLUSION.search(query):
        return EmergencyKind.MEDICAL
    return None

def is_emergency_query(query: str) -> bool:
    return detect_emergency(query) is not None

MEDICAL_EMERGENCY_RESPONSE = (
    "🚨 **EMERGENCY WARNING:** If you or someone near you is experiencing severe symptoms such as "
    "chest pain, difficulty breathing, sudden numbness or weakness, a seizure, or uncontrollable bleeding, "
    "please call emergency services (e.g., 112 in India, 911 in the US, or 999 in the UK) "
    "immediately or go to the nearest emergency room."
)

CRISIS_RESPONSE = (
    "🚨 **EMERGENCY WARNING:** I'm really sorry you're going through this. You don't have to face it alone.\n\n"
    "If you might act on these thoughts or are in immediate danger, please call your local emergency number now "
    "(112 in India, 911 in the US, 999 in the UK).\n\n"
    "You can also talk to someone right away: **India:** Tele-MANAS 14416 or 1-800-891-4416; "
    "**US:** call or text 988; elsewhere see [https://findahelpline.com](https://findahelpline.com)."
)

EMERGENCY_RESPONSE = MEDICAL_EMERGENCY_RESPONSE

def get_emergency_response(kind: EmergencyKind = EmergencyKind.MEDICAL) -> str:
    return CRISIS_RESPONSE if kind == EmergencyKind.SELF_HARM else MEDICAL_EMERGENCY_RESPONSE

DISCLAIMER_TEXT = (
    "\n\n***\n\n"
    "**Disclaimer:** This explanation is for educational purposes only and is not a substitute for "
    "professional medical advice, diagnosis, or treatment. Always consult a licensed healthcare provider "
    "for medical decisions."
)

def append_disclaimer(response_text: str, intent: Optional[Any] = None) -> str:
    if intent is not None:
        intent_val = getattr(intent, "value", intent)
        if str(intent_val).upper() == "CASUAL" or "CASUAL" in str(intent).upper():
            return response_text
    if DISCLAIMER_TEXT.strip() in response_text:
        return response_text
    return response_text + DISCLAIMER_TEXT
