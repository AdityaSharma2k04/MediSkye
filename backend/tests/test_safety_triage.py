import pytest
from app.rag.safety import (
    EmergencyKind,
    detect_emergency,
    is_emergency_query,
    get_emergency_response,
    MEDICAL_EMERGENCY_RESPONSE,
    CRISIS_RESPONSE,
)
from app.rag.output_filter import scan_output, SAFE_FALLBACK


def test_detect_emergency_self_harm():
    assert detect_emergency("I am feeling suicidal and need help") == EmergencyKind.SELF_HARM
    assert detect_emergency("I want to end my life") == EmergencyKind.SELF_HARM
    assert detect_emergency("I want to die") == EmergencyKind.SELF_HARM
    assert detect_emergency("thinking of hurting myself") == EmergencyKind.SELF_HARM
    assert detect_emergency("self-harm thoughts") == EmergencyKind.SELF_HARM
    assert is_emergency_query("I am suicidal") is True


def test_detect_emergency_acute_medical():
    assert detect_emergency("I can't breathe") == EmergencyKind.MEDICAL
    assert detect_emergency("severe chest pain and pressure") == EmergencyKind.MEDICAL
    assert detect_emergency("coughing up blood") == EmergencyKind.MEDICAL
    assert detect_emergency("having a heart attack right now") == EmergencyKind.MEDICAL
    assert detect_emergency("sudden stroke symptoms") == EmergencyKind.MEDICAL
    assert is_emergency_query("I cannot breathe") is True


def test_detect_emergency_risk_question_exclusions():
    """Verify that clinical questions about risk/prevention are NOT classified as emergencies."""
    assert detect_emergency("Does my high LDL raise risk of heart attack?") is None
    assert detect_emergency("What is the chance of stroke with high blood pressure?") is None
    assert detect_emergency("How to prevent a heart attack?") is None
    assert detect_emergency("Family history of heart attack") is None
    assert detect_emergency("What is a stroke?") is None
    assert is_emergency_query("Does my high cholesterol raise risk of heart attack?") is False


def test_get_emergency_response():
    assert get_emergency_response(EmergencyKind.SELF_HARM) == CRISIS_RESPONSE
    assert get_emergency_response(EmergencyKind.MEDICAL) == MEDICAL_EMERGENCY_RESPONSE
    assert "Tele-MANAS" in CRISIS_RESPONSE
    assert "911" in MEDICAL_EMERGENCY_RESPONSE or "112" in MEDICAL_EMERGENCY_RESPONSE


def test_output_filter_negation_awareness():
    """Verify negative lookbehinds allow safe medical advice that negates dangerous actions."""
    safe_advice_1 = "You should not stop taking your medication without talking to your doctor."
    safe_advice_2 = "Never double your dose even if you missed yesterday's pill."
    safe_advice_3 = "Don't increase your insulin dose on your own."
    safe_advice_4 = "Do not stop your treatment abruptly."

    for advice in [safe_advice_1, safe_advice_2, safe_advice_3, safe_advice_4]:
        is_safe, reason = scan_output(advice)
        assert is_safe is True, f"Failed for safe advice: {advice} (reason={reason})"


def test_output_filter_blocks_dangerous_advice():
    """Verify dangerous advice triggers output filter."""
    danger_1 = "You should double your dose immediately."
    danger_2 = "Stop all your medications today."
    danger_3 = "Inject 500 units of insulin."

    for danger in [danger_1, danger_2, danger_3]:
        is_safe, reason = scan_output(danger)
        assert is_safe is False, f"Failed to block dangerous advice: {danger}"
        assert "dangerous_advice" in reason


def test_output_filter_persona_break_not_blocking_standard_disclaimer():
    """Standard medical disclaimer should not be blocked as a persona break."""
    disclaimer = "I am not a medical professional, but here is what the clinical literature says."
    is_safe, reason = scan_output(disclaimer)
    assert is_safe is True, f"Legitimate medical disclaimer should not trigger persona break: {reason}"

