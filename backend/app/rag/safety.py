EMERGENCY_KEYWORDS = [
    "chest pain",
    "heart attack",
    "stroke",
    "cannot breathe",
    "shortness of breath",
    "severe bleeding",
    "unconscious",
    "seizure",
    "suicide",
    "overdose",
    "anaphylaxis",
]

DISCLAIMER_TEXT = (
    "\n\n***\n\n"
    "**Disclaimer:** This explanation is for educational purposes only and is not a substitute for "
    "professional medical advice, diagnosis, or treatment. Always consult a licensed healthcare provider "
    "for medical decisions."
)

EMERGENCY_RESPONSE = (
    "🚨 **EMERGENCY WARNING:** If you or someone near you is experiencing severe symptoms such as "
    "chest pain, difficulty breathing, sudden numbness, or uncontrollable bleeding, please call emergency services "
    "(e.g., 911 or your local emergency hotline) immediately or go to the nearest emergency room."
)


def is_emergency_query(query: str) -> bool:
    lowered = query.lower()
    return any(keyword in lowered for keyword in EMERGENCY_KEYWORDS)


def get_emergency_response() -> str:
    return EMERGENCY_RESPONSE


def append_disclaimer(response_text: str) -> str:
    if DISCLAIMER_TEXT.strip() in response_text:
        return response_text
    return response_text + DISCLAIMER_TEXT
