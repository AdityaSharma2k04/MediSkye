import uuid
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.db.database import AsyncSessionLocal
from app.db.models import User
from app.core.auth import get_password_hash
from tests.conftest import TEST_PASSWORD
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

POSITIVES = [
    # Hindi (10)
    ("मुझे आत्महत्या करनी है", EmergencyKind.SELF_HARM, "Hindi"),
    ("मैं मरना चाहता हूँ", EmergencyKind.SELF_HARM, "Hindi"),
    ("अब मैं जीना नहीं चाहती", EmergencyKind.SELF_HARM, "Hindi"),
    ("mujhe atmahatya karni hai", EmergencyKind.SELF_HARM, "Hindi"),
    ("jeena nahi chahta", EmergencyKind.SELF_HARM, "Hindi"),
    ("मेरे सीने में तेज दर्द हो रहा है", EmergencyKind.MEDICAL, "Hindi"),
    ("सांस लेने में दिक्कत हो रही है", EmergencyKind.MEDICAL, "Hindi"),
    ("मुझे दिल का दौरा पड़ रहा है", EmergencyKind.MEDICAL, "Hindi"),
    ("seene me bahut dard ho raha hai", EmergencyKind.MEDICAL, "Hindi"),
    ("saans lene me takleef ho rahi hai", EmergencyKind.MEDICAL, "Hindi"),
    # Spanish (9)
    ("quiero morir", EmergencyKind.SELF_HARM, "Spanish"),
    ("quiero matarme", EmergencyKind.SELF_HARM, "Spanish"),
    ("quiero quitarme la vida", EmergencyKind.SELF_HARM, "Spanish"),
    ("no quiero vivir más", EmergencyKind.SELF_HARM, "Spanish"),
    ("tengo un dolor en el pecho muy fuerte", EmergencyKind.MEDICAL, "Spanish"),
    ("no puedo respirar", EmergencyKind.MEDICAL, "Spanish"),
    ("tengo una hemorragia severa", EmergencyKind.MEDICAL, "Spanish"),
    ("creo que tengo un infarto", EmergencyKind.MEDICAL, "Spanish"),
    ("dificultad para respirar", EmergencyKind.MEDICAL, "Spanish"),
    # French (9)
    ("je veux mourir", EmergencyKind.SELF_HARM, "French"),
    ("j'ai envie de me tuer", EmergencyKind.SELF_HARM, "French"),
    ("je veux me suicider", EmergencyKind.SELF_HARM, "French"),
    ("mettre fin à ma vie", EmergencyKind.SELF_HARM, "French"),
    ("j'ai une douleur dans la poitrine", EmergencyKind.MEDICAL, "French"),
    ("je n'arrive pas à respirer", EmergencyKind.MEDICAL, "French"),
    ("je fais un infarctus", EmergencyKind.MEDICAL, "French"),
    ("saignement abondant", EmergencyKind.MEDICAL, "French"),
    ("difficulté à respirer", EmergencyKind.MEDICAL, "French"),
    # German (9)
    ("ich will sterben", EmergencyKind.SELF_HARM, "German"),
    ("ich möchte mich umbringen", EmergencyKind.SELF_HARM, "German"),
    ("mir das leben nehmen", EmergencyKind.SELF_HARM, "German"),
    ("ich habe suizidgedanken", EmergencyKind.SELF_HARM, "German"),
    ("ich habe starke schmerzen in der brust", EmergencyKind.MEDICAL, "German"),
    ("ich bekomme keine luft mehr", EmergencyKind.MEDICAL, "German"),
    ("atemnot und druck auf der brust", EmergencyKind.MEDICAL, "German"),
    ("ich habe einen herzinfarkt", EmergencyKind.MEDICAL, "German"),
    ("starke blutung", EmergencyKind.MEDICAL, "German"),
]


@pytest.mark.parametrize("query,expected_kind,expected_lang", POSITIVES)
def test_multilingual_emergency_detection(query, expected_kind, expected_lang):
    assert detect_emergency(query) == expected_kind
    assert detect_emergency_language(query) == expected_lang


NEGATIVES = [
    "दिल का दौरा पड़ने का क्या जोखिम है?",
    "हार्ट अटैक से बचाव के तरीके",
    "स्ट्रोक क्या होता है?",
    "dil ka daura padne ka khatra",
    "dil ke daure ka karan kya hai",
    "cuál es el riesgo de infarto?",
    "cómo prevenir un ataque cardíaco",
    "qué es un ictus y cuáles son las causas",
    "riesgo de infarto",
    "prevención de infarto",
    "quels sont les risques de crise cardiaque?",
    "comment prévenir un infarctus",
    "qu'est-ce qu'un avc?",
    "antécédents de crise cardiaque",
    "prévention de l'infarctus",
    "was ist das risiko eines herzinfarkts?",
    "wie kann man einem schlaganfall vorbeugen?",
    "ursachen von herzinfarkt",
    "was ist ein schlaganfall?",
    "vorbeugung von schlaganfall",
]


@pytest.mark.parametrize("query", NEGATIVES)
def test_multilingual_risk_and_educational_exclusions(query):
    assert detect_emergency(query) is None
    assert detect_emergency_language(query) is None


@pytest.mark.parametrize("lang,expected_medical,expected_crisis", [
    ("Hindi", _HI_MEDICAL, _HI_CRISIS),
    ("Spanish", _ES_MEDICAL, _ES_CRISIS),
    ("French", _FR_MEDICAL, _FR_CRISIS),
    ("German", _DE_MEDICAL, _DE_CRISIS),
    ("English", MEDICAL_EMERGENCY_RESPONSE, CRISIS_RESPONSE),
])
def test_localized_banners(lang, expected_medical, expected_crisis):
    assert get_emergency_response(EmergencyKind.MEDICAL, lang) == expected_medical
    assert get_emergency_response(EmergencyKind.SELF_HARM, lang) == expected_crisis


@pytest.mark.parametrize("alias,expected_medical,expected_crisis", [
    ("hi", _HI_MEDICAL, _HI_CRISIS),
    ("hi-IN", _HI_MEDICAL, _HI_CRISIS),
    ("es", _ES_MEDICAL, _ES_CRISIS),
    ("es-ES", _ES_MEDICAL, _ES_CRISIS),
    ("fr", _FR_MEDICAL, _FR_CRISIS),
    ("fr-FR", _FR_MEDICAL, _FR_CRISIS),
    ("de", _DE_MEDICAL, _DE_CRISIS),
    ("de-DE", _DE_MEDICAL, _DE_CRISIS),
    ("en", MEDICAL_EMERGENCY_RESPONSE, CRISIS_RESPONSE),
    ("en-US", MEDICAL_EMERGENCY_RESPONSE, CRISIS_RESPONSE),
    (None, MEDICAL_EMERGENCY_RESPONSE, CRISIS_RESPONSE),
    ("unknown_lang", MEDICAL_EMERGENCY_RESPONSE, CRISIS_RESPONSE),
])
def test_banner_language_aliases_and_default(alias, expected_medical, expected_crisis):
    assert get_emergency_response(EmergencyKind.MEDICAL, alias) == expected_medical
    assert get_emergency_response(EmergencyKind.SELF_HARM, alias) == expected_crisis


@pytest.mark.asyncio
async def test_hindi_chest_pain_returns_localized_banner():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        email = f"hindi_emerg_{uuid.uuid4().hex[:8]}@test.com"
        async with AsyncSessionLocal() as session:
            session.add(User(
                email=email,
                hashed_password=get_password_hash(TEST_PASSWORD),
                phi_consent_granted=True,
                memory_consent_granted=True,
            ))
            await session.commit()
        login = await ac.post("/login", data={"username": email, "password": TEST_PASSWORD})
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        with patch("app.api.v1.endpoints.query.process_chat_memory_extraction", new=AsyncMock()):
            res = await ac.post("/query", json={"query": "मुझे सीने में तेज़ दर्द हो रहा है"}, headers=headers)
        assert res.status_code == 200, res.text
        assert "आपातकालीन चेतावनी" in res.text, f"Missing Hindi emergency title in: {res.text}"
        assert "If you or someone near you" not in res.text, f"English banner found in: {res.text}"
