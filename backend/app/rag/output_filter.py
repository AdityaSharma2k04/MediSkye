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
    r"(?<!not )(?<!never )(?<!don't )(?<!do not )(?:double|triple|quadruple|10x|increase)\s+(?:your|the|their)\s+(?:dose|dosage|insulin|medication)",
    r"(?<!not )(?<!never )(?<!don't )(?<!do not )stop\s+(?:all\s+|taking\s+|your\s+)*(?:medications?|medicine|treatment)",
    r"(?:inject|take|consume)\s+\d{3,}\s*(?:mg|ml|units)",
]

_COMPILED_PERSONA = [re.compile(p, re.IGNORECASE) for p in PERSONA_BREAK_PATTERNS]
_COMPILED_DANGER = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_ADVICE_PATTERNS]


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
        if pattern.search(text):
            return False, f"dangerous_advice: {pattern.pattern}"

    return True, None
