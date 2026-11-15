"""Output filter for detecting possible prompt injection success markers.

MONITORING ONLY — detects and logs. Does NOT modify responses.
"""
import re
import logging

logger = logging.getLogger(__name__)

SAFE_FALLBACK = (
    "I can't give a reliable answer to that. Please discuss this with your doctor or pharmacist, "
    "and don't change any medication without their advice."
)

PERSONA_BREAK_PATTERNS = [
    r"\bas an ai language model\b",
    r"\bi'?m just an ai\b",
    r"\bdan mode\b",
    r"\bfreedomgpt\b",
    r"\bdeveloper mode\b",
    r"\bjailbreak\b",
    r"\bignore previous instructions\b",
    r"\bignore all instructions\b",
    r"\bignore prior instructions\b",
]

DANGEROUS_ADVICE_PATTERNS = [
    r"(?:double|triple|quadruple|10x|increase)\s+(?:your|the|their)\s+(?:dose|dosage|insulin|medication)",
    r"stop\s+(?:all\s+|taking\s+|your\s+)*(?:medications?|medicine|treatment)",
    r"(?:inject|take|consume)\s+\d{3,}\s*(?:mg|ml|units)",
]

_OVERDOSE_PATTERN = r"(?:inject|take|consume)\s+\d{3,}\s*(?:mg|ml|units)"

_COMPILED_PERSONA = [re.compile(p, re.IGNORECASE) for p in PERSONA_BREAK_PATTERNS]
_COMPILED_DANGER = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_ADVICE_PATTERNS]

_NEGATION_PREFIX_RE = re.compile(
    r"\b(?:do\s+not|don['’‘]t|should\s+not|shouldn['’‘]t|would\s+not|wouldn['’‘]t|"
    r"must\s+not|mustn['’‘]t|can\s*not|can['’‘]t|never|not|avoid|against|instead\s+of|without)\b"
    r"(?:\s+\w+){0,4}\s*$",
    re.IGNORECASE,
)


def sanitize_clinical_prose(text: str, is_followup: bool = False) -> str:
    """
    Deterministic clinical prose sanitizer applied to final assistant responses and generated summaries.
    - Replaces raw HTML entity &amp; with &.
    - Replaces leaked raw PDF filenames (e.g. Qureshi.pdf, Menon.pdf, Verma.pdf, report-1.pdf) with 'your laboratory report'.
    - Replaces over-certain or panicky phrases with methodical, balanced phrasing.
    """
    if not text or not isinstance(text, str):
        return text or ""

    s = text.replace("&amp;", "&")

    # Replace leaked raw PDF filenames
    s = re.sub(r"\b[A-Za-z0-9_-]+\.pdf\b", "your laboratory report", s, flags=re.IGNORECASE)

    # Replace over-certain phrases
    s = re.sub(r"\bhighly likely\b", "a possible", s, flags=re.IGNORECASE)

    # Replace panic / reassurance phrases
    s = re.sub(
        r"There is absolutely no need to panic, as you are in a very strong and healthy position overall\.",
        "While several markers on your report need attention, your core metabolic and cardiovascular readings provide a steady foundation to work from.",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\b(?:there\s+is\s+)?(?:absolutely\s+)?no\s+need\s+to\s+(?:panic|worry)\b",
        "these findings can be addressed methodically with your clinician",
        s,
        flags=re.IGNORECASE,
    )

    return s


def scan_output(text: str) -> tuple[bool, str | None]:
    """
    Scan LLM output for possible injection success markers.

    Returns:
        (is_safe, reason)
        - is_safe=True, reason=None → no concerns
        - is_safe=False, reason="persona_break: <pattern>" → logged, not blocked
    """
    if not text:
        return True, None

    for pattern in _COMPILED_PERSONA:
        if pattern.search(text):
            return False, f"persona_break: {pattern.pattern}"

    for pattern in _COMPILED_DANGER:
        is_overdose = (pattern.pattern == _OVERDOSE_PATTERN)
        for m in pattern.finditer(text):
            if not is_overdose:
                prefix = text[max(0, m.start() - 60):m.start()]
                if _NEGATION_PREFIX_RE.search(prefix):
                    continue
            return False, f"dangerous_advice: {pattern.pattern}"

    return True, None
