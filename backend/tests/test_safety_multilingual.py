import pytest
from app.rag.safety import (
    EmergencyKind,
    detect_emergency,
    detect_emergency_language,
    get_emergency_response,
    MEDICAL_EMERGENCY_RESPONSE,
    CRISIS_RESPONSE,
    _HI_MEDICAL,
    _HI_CRISIS,
    _ES_MEDICAL,
    _ES_CRISIS,
    _FR_MEDICAL,
    _FR_CRISIS,
    _DE_MEDICAL,
    _DE_CRISIS,
)


@pytest.mark.parametrize("query,expected_kind,expected_lang", [
    # Hindi Devanagari Self-Harm
    ("मुझे आत्महत्या करनी है", EmergencyKind.SELF_HARM, "Hindi"),
    ("मैं मरना चाहता हूँ", EmergencyKind.SELF_HARM, "Hindi"),
    ("अब मैं जीना नहीं चाहती", EmergencyKind.SELF_HARM, "Hindi"),
    ("खुदकुशी करने का मन कर रहा है", EmergencyKind.SELF_HARM, "Hindi"),
    ("अपनी जान दे दूंगा", EmergencyKind.SELF_HARM, "Hindi"),
    # Hindi Hinglish Self-Harm
    ("mujhe atmahatya karni hai", EmergencyKind.SELF_HARM, "Hindi"),
    ("khudkushi karne ka mann hai", EmergencyKind.SELF_HARM, "Hindi"),
    ("jeene ki iccha nahi hai", EmergencyKind.SELF_HARM, "Hindi"),
    ("jeena nahi chahta", EmergencyKind.SELF_HARM, "Hindi"),
    # Hindi Devanagari Medical
    ("मेरे सीने में तेज दर्द हो रहा है", EmergencyKind.MEDICAL, "Hindi"),
    ("सांस लेने में दिक्कत हो रही है", EmergencyKind.MEDICAL, "Hindi"),
    ("मुझे दिल का दौरा पड़ रहा है", EmergencyKind.MEDICAL, "Hindi"),
    ("खांसी में खून आ रहा है", EmergencyKind.MEDICAL, "Hindi"),
    # Hindi Hinglish Medical
    ("seene me bahut dard ho raha hai", EmergencyKind.MEDICAL, "Hindi"),
    ("saans lene me takleef ho rahi hai", EmergencyKind.MEDICAL, "Hindi"),
    ("dil ka daura pad raha hai", EmergencyKind.MEDICAL, "Hindi"),
    ("khansi me khoon aa raha hai", EmergencyKind.MEDICAL, "Hindi"),
    # Spanish Self-Harm
    ("quiero morir", EmergencyKind.SELF_HARM, "Spanish"),
    ("quiero matarme", EmergencyKind.SELF_HARM, "Spanish"),
    ("quiero quitarme la vida", EmergencyKind.SELF_HARM, "Spanish"),
    ("no quiero vivir más", EmergencyKind.SELF_HARM, "Spanish"),
    # Spanish Medical
    ("tengo un dolor en el pecho muy fuerte", EmergencyKind.MEDICAL, "Spanish"),
    ("no puedo respirar", EmergencyKind.MEDICAL, "Spanish"),
    ("tengo una hemorragia severa", EmergencyKind.MEDICAL, "Spanish"),
    ("creo que tengo un infarto", EmergencyKind.MEDICAL, "Spanish"),
    # French Self-Harm
    ("je veux mourir", EmergencyKind.SELF_HARM, "French"),
    ("j'ai envie de me tuer", EmergencyKind.SELF_HARM, "French"),
    ("je veux me suicider", EmergencyKind.SELF_HARM, "French"),
    ("mettre fin à ma vie", EmergencyKind.SELF_HARM, "French"),
    # French Medical
    ("j'ai une douleur dans la poitrine", EmergencyKind.MEDICAL, "French"),
    ("je n'arrive pas à respirer", EmergencyKind.MEDICAL, "French"),
    ("je fais un infarctus", EmergencyKind.MEDICAL, "French"),
    ("saignement abondant", EmergencyKind.MEDICAL, "French"),
    # German Self-Harm
    ("ich will sterben", EmergencyKind.SELF_HARM, "German"),
    ("ich möchte mich umbringen", EmergencyKind.SELF_HARM, "German"),
    ("mir das leben nehmen", EmergencyKind.SELF_HARM, "German"),
    ("ich habe suizidgedanken", EmergencyKind.SELF_HARM, "German"),
    # German Medical
    ("ich habe starke schmerzen in der brust", EmergencyKind.MEDICAL, "German"),
    ("ich bekomme keine luft mehr", EmergencyKind.MEDICAL, "German"),
    ("atemnot und druck auf der brust", EmergencyKind.MEDICAL, "German"),
    ("ich habe einen herzinfarkt", EmergencyKind.MEDICAL, "German"),
])
def test_multilingual_emergency_detection(query, expected_kind, expected_lang):
    assert detect_emergency(query) == expected_kind
    assert detect_emergency_language(query) == expected_lang


@pytest.mark.parametrize("query", [
    # Hindi Exclusions
    "दिल का दौरा पड़ने का क्या जोखिम है?",
    "हार्ट अटैक से बचाव के तरीके",
    "स्ट्रोक क्या होता है?",
    "dil ka daura padne ka khatra",
    # Spanish Exclusions
    "cuál es el riesgo de infarto?",
    "cómo prevenir un ataque cardíaco",
    "qué es un ictus y cuáles son las causas",
    # French Exclusions
    "quels sont les risques de crise cardiaque?",
    "comment prévenir un infarctus",
    "qu'est-ce qu'un avc?",
    # German Exclusions
    "was ist das risiko eines herzinfarkts?",
    "wie kann man einem schlaganfall vorbeugen?",
    "ursachen von herzinfarkt",
])
def test_multilingual_risk_and_educational_exclusions(query):
    assert detect_emergency(query) is None


@pytest.mark.parametrize("lang,expected_medical,expected_crisis", [
    ("Hindi", _HI_MEDICAL, _HI_CRISIS),
    ("hi", _HI_MEDICAL, _HI_CRISIS),
    ("hi-IN", _HI_MEDICAL, _HI_CRISIS),
    ("Spanish", _ES_MEDICAL, _ES_CRISIS),
    ("es", _ES_MEDICAL, _ES_CRISIS),
    ("es-ES", _ES_MEDICAL, _ES_CRISIS),
    ("French", _FR_MEDICAL, _FR_CRISIS),
    ("fr", _FR_MEDICAL, _FR_CRISIS),
    ("fr-FR", _FR_MEDICAL, _FR_CRISIS),
    ("German", _DE_MEDICAL, _DE_CRISIS),
    ("de", _DE_MEDICAL, _DE_CRISIS),
    ("de-DE", _DE_MEDICAL, _DE_CRISIS),
    ("English", MEDICAL_EMERGENCY_RESPONSE, CRISIS_RESPONSE),
    ("en", MEDICAL_EMERGENCY_RESPONSE, CRISIS_RESPONSE),
    ("en-US", MEDICAL_EMERGENCY_RESPONSE, CRISIS_RESPONSE),
    (None, MEDICAL_EMERGENCY_RESPONSE, CRISIS_RESPONSE),
    ("unknown_lang", MEDICAL_EMERGENCY_RESPONSE, CRISIS_RESPONSE),
])
def test_multilingual_emergency_banners(lang, expected_medical, expected_crisis):
    assert get_emergency_response(EmergencyKind.MEDICAL, lang) == expected_medical
    assert get_emergency_response(EmergencyKind.SELF_HARM, lang) == expected_crisis
