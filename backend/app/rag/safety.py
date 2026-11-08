import re
import unicodedata
from enum import Enum
from typing import Optional, Any

class EmergencyKind(str, Enum):
    MEDICAL = "medical"
    SELF_HARM = "self_harm"

_SELF_HARM = re.compile(
    r"\b(suicid\w*|kill(?:ing)? myself|end(?:ing)? my (?:own )?life|take my (?:own )?life|"
    r"want(?:ed)? to die|(?:don'?t|do not|no longer) want to "
    r"(?:live(?!\s+(?:on|off|without|near|alone|with\s+(?!(?:this|it|that|myself)\b))\b)|be alive)|"
    r"better off dead|self[- ]?harm|hurt(?:ing)? myself)\b",
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

def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)

def _rx(pattern: str) -> "re.Pattern":
    return re.compile(_nfc(pattern), re.I)

_LOCALIZED = {
    "Hindi": {
        "self_harm": _rx(
            r"आत्महत्या|आत्म-हत्या|ख़ुदकुशी|खुदकुशी|खुद\s*कुशी"
            r"|मरना\s+चाह(?:ता|ती|ते)|मर\s+जाना\s+चाह(?:ता|ती|ते)"
            r"|जीना\s+नहीं\s+चाह(?:ता|ती|ते)|जीने\s+की\s+इच्छा\s+नहीं"
            r"|अपनी\s+जान\s+(?:दे|ले)|खुद\s+को\s+(?:नुकसान\s+पहुँ?चा|चोट\s+पहुँ?चा|खत्म\s+कर)"
            r"|\b(?:a+tma?[\s-]?hatya|khud[\s-]?kh?ushi)\b"
            r"|\bmar(?:na|ne)\s+(?:chahta|chahti|chahte)\b|\bmar\s+jana\s+(?:chahta|chahti)\b"
            r"|\bjeena\s+nahi\s+(?:chahta|chahti)\b|\bjeene\s+ki\s+(?:ichha|iccha)\s+nahi\b"
            r"|\b(?:apni|apna)\s+jaan\s+(?:de|le)\b|\bkhud\s+ko\s+khatam\s+kar"
        ),
        "medical": _rx(
            r"(?:सीने|छाती)\s+में\s+(?:तेज़?\s+|बहुत\s+)?(?:दर्द|जकड़न|दबाव|भारीपन)"
            r"|सा[ँं]स\s+(?:नहीं\s+आ|लेने\s+में\s+(?:तकलीफ़?|कठिनाई|दिक्कत|परेशानी))|दम\s+घुट"
            r"|दिल\s+का\s+दौरा\s+पड़\s+रहा|मिर्गी\s+का\s+दौरा|दौरे?\s+पड़"
            r"|बेहोश|(?:ख़|ख)ून\s+की\s+उल्टी|(?:ख़|ख)ून\s+(?:बहुत\s+)?(?:ज़्यादा|ज्यादा)\s+बह"
            r"|(?:खांसी|खाँसी)\s+में\s+(?:ख़|ख)ून|ओवरडोज़?|(?:ज़हर|जहर)\s+खा"
            r"|\b(?:seene|sine|chhati|chhaati|chati)\s+(?:me|mein|mai|main)\s+(?:tez\s+|bahut\s+|zyada\s+)?(?:dard|jakdan|dabav|bhaaripan)\b"
            r"|\bsaans\s+(?:nahi|nahin)\s+aa|\bsaans\s+lene\s+(?:me|mein)\s+(?:takleef|dikkat|pareshani)\b|\bdam\s+ghut"
            r"|\bdil\s+ka\s+daura\s+pad\s+raha\b|\bmirgi\s+ka\s+daura\b|\bdaura\s+pad\b|\bbehosh\b"
            r"|\bkhoon\s+ki\s+ulti\b|\b(?:zyada|jyada)\s+khoon\s+(?:beh|bah)|\bkhansi\s+(?:me|mein)\s+khoon\b"
            r"|\b(?:zeher|jahar)\s+kha"
        ),
        "acute": _rx(r"दिल\s+का\s+दौरा|हार्ट\s*अटैक|लकवा|पक्षाघात|स्ट्रोक|ब्रेन\s+हैमरेज|\bdil\s+ka\s+daura\b|\blakwa\b|\bparalysis\b"),
        "exclusion": _rx(r"जोखिम|(?:ख़|ख)तरा|रोकथाम|बचाव|पारिवारिक\s+इतिहास|क्या\s+है|क्या\s+होता\s+है|कारण|\b(?:risk|khatra|bachav|rokthaam|kya\s+hai|kya\s+hota\s+hai|karan)\b"),
    },
    "Spanish": {
        "self_harm": _rx(
            r"\b(?:quiero|quisiera)\s+morir(?:me)?\b|\bquiero\s+matarme\b|\bme\s+voy\s+a\s+matar\b"
            r"|\bquitarme\s+la\s+vida\b|\b(?:acabar|terminar)\s+con\s+mi\s+vida\b"
            r"|\bno\s+quiero\s+(?:seguir\s+)?vivir(?!\s+(?:de|sin|cerca|solo|sola)\b|\s+con\s+(?!(?:esto|eso|ello)\b))"
            r"|\bhacerme\s+daño\b|\bautolesi\w+"
        ),
        "medical": _rx(
            r"\bdolor\s+(?:de|en\s+el)\s+pecho\b|\bdolor\s+tor[aá]cico\b|\b(?:opresi[oó]n|presi[oó]n)\s+(?:en\s+el|del)\s+pecho\b"
            r"|\bno\s+puedo\s+respirar\b|\bme\s+cuesta\s+respirar\b|\bdificultad\s+(?:para|al)\s+respirar\b"
            r"|\bfalta\s+de\s+aire\b|\bme\s+falta\s+el\s+aire\b|\bsangrado\s+(?:abundante|severo|grave|intenso)\b|\bhemorragia\b"
            r"|\b(?:tos|toso)\s+(?:con\s+)?sangre\b|\bescupo\s+sangre\b|\binconsciente\b|\bconvulsi[oó]n(?:es)?\b"
            r"|\bataque\s+epil[eé]ptico\b|\bsobredosis\b|\banafila\w+|\benvenenamiento\b"
            r"|\b(?:tengo|estoy\s+teniendo|creo\s+que\s+tengo)\s+un\s+(?:infarto|ictus|derrame)\b"
        ),
        "acute": _rx(r"\b(?:infarto|ataque\s+(?:al\s+coraz[oó]n|card[ií]aco)|ictus|derrame\s+cerebral|accidente\s+cerebrovascular)\b"),
        "exclusion": _rx(r"\b(?:riesgo|probabilidad\s+de|prevenir|prevenci[oó]n|antecedentes(?:\s+familiares)?\s+de|qu[eé]\s+es|causas?)\b"),
    },
    "French": {
        "self_harm": _rx(
            r"\b(?:je\s+veux|j['’]ai\s+envie\s+de)\s+(?:mourir|me\s+tuer)\b|\benvie\s+de\s+mourir\b|\bme\s+suicider\b"
            r"|\bmettre\s+fin\s+[àa]\s+(?:mes\s+jours|ma\s+vie)\b|\ben\s+finir\s+avec\s+la\s+vie\b"
            r"|\b(?:ne\s+veux|veux)\s+plus\s+vivre(?!\s+(?:sans|de|pr[eè]s|seule?)\b|\s+avec\s+(?!(?:[cç]a|cela)\b))"
            r"|\bplus\s+envie\s+de\s+vivre\b|\bme\s+faire\s+du\s+mal\b|\bautomutil\w+|\bscarification\b"
        ),
        "medical": _rx(
            r"\bdouleurs?\s+(?:thoraciques?|(?:dans|[àa])\s+la\s+poitrine)\b|\bserrement\s+(?:dans\s+la\s+|de\s+la\s+)?poitrine\b"
            r"|\boppression\s+(?:thoracique|dans\s+la\s+poitrine)\b"
            r"|\b(?:n['’]arrive\s+pas|ne\s+peux\s+(?:pas|plus)|ne\s+parviens\s+pas)\s+[àa]?\s*respirer\b"
            r"|\bdifficult[ée]s?\s+[àa]\s+respirer\b|\bh[ée]morragie\b|\bsaignement\s+(?:abondant|important|grave|incontr[oô]l[ée])\b"
            r"|\bcrache\s+(?:du\s+)?sang\b|\bcrachats?\s+de\s+sang\b|\binconscient\b|\bperdu\s+connaissance\b"
            r"|\bconvulsions?\b|\bcrise\s+d['’][ée]pilepsie\b|\bsurdose\b|\boverdose\b|\banaphyla\w+|\bempoisonnement\b"
            r"|\bje\s+(?:fais|suis\s+en\s+train\s+de\s+faire)\s+(?:un|une)\s+(?:infarctus|avc|crise\s+cardiaque)\b"
        ),
        "acute": _rx(r"\b(?:crise\s+cardiaque|infarctus|avc|accident\s+vasculaire\s+c[ée]r[ée]bral)\b"),
        "exclusion": _rx(r"\b(?:risques?|pr[ée]venir|pr[ée]vention|ant[ée]c[ée]dents(?:\s+familiaux)?\s+de|qu['’]est-ce\s+(?:que|qu['’]))\b"),
    },
    "German": {
        "self_harm": _rx(
            r"\bsuizid\w*|\bselbstmord\w*|\bselbsttötung\w*|\bmich\s+umbringen\b|\bmir\s+das\s+leben\s+nehmen\b"
            r"|\b(?:will|möchte)\s+(?:nicht\s+mehr\s+leben|sterben)\b|\bselbstverletz\w+|\bmich\s+(?:selbst\s+)?verletzen\b"
            r"|\bmir\s+(?:etwas\s+)?antun\b|\bmich\s+ritzen\b"
        ),
        "medical": _rx(
            r"\bbrustschmerz\w*|\bschmerzen\s+in\s+der\s+brust\b|\bdruck\s+(?:auf|in)\s+der\s+brust\b|\bbrustenge\b"
            r"|\bengegef[üu]hl\s+in\s+der\s+brust\b|\b(?:bekomme|kriege)\s+keine\s+luft\b|\bkeine\s+luft\s+(?:mehr\s+)?(?:bekommen|kriegen)\b"
            r"|\bkann\s+nicht\s+(?:mehr\s+)?atmen\b|\batemnot\b|\bluftnot\b|\bstarke[rn]?\s+blutung\w*|\bblutet\s+stark\b"
            r"|\bblut\s+(?:husten|gehustet)\b|\bhustet\s+blut\b|\bbewusstlos\b|\bkrampfanfall\b|\bepileptischer\s+anfall\b"
            r"|\b[üu]berdosis\b|\banaphyla\w+|\bvergiftung\b"
            r"|\b(?:habe|bekomme|erleide)\s+(?:gerade\s+)?(?:einen|eine)\s+(?:herzinfarkt|schlaganfall)\b"
        ),
        "acute": _rx(r"\b(?:herzinfarkt|schlaganfall|hirnschlag)\b"),
        "exclusion": _rx(r"\b(?:risiko|vorbeugen|vorbeugung|pr[äa]vention|vorbeugend|famili[äa]r\w*|was\s+ist|ursachen?)\b"),
    },
}

def _localized_hit(query: str):
    q = _nfc(query)
    for key, kind in (("self_harm", EmergencyKind.SELF_HARM), ("medical", EmergencyKind.MEDICAL)):
        for lang, pats in _LOCALIZED.items():
            if pats[key].search(q):
                return kind, lang
    for lang, pats in _LOCALIZED.items():
        if pats["acute"].search(q) and not pats["exclusion"].search(q):
            return EmergencyKind.MEDICAL, lang
    return None

def detect_emergency(query: str) -> Optional[EmergencyKind]:
    if not query:
        return None
    if _SELF_HARM.search(query):
        return EmergencyKind.SELF_HARM
    localized = _localized_hit(query)
    if localized and localized[0] == EmergencyKind.SELF_HARM:
        return EmergencyKind.SELF_HARM
    if _MEDICAL.search(query):
        return EmergencyKind.MEDICAL
    if _ACUTE_UNQUALIFIED.search(query) and not _RISK_QUESTION_EXCLUSION.search(query):
        return EmergencyKind.MEDICAL
    if localized:
        return localized[0]
    return None

def detect_emergency_language(query: str) -> Optional[str]:
    if not query:
        return None
    hit = _localized_hit(query)
    return hit[1] if hit else None

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

_HI_MEDICAL = (
    "🚨 **आपातकालीन चेतावनी (EMERGENCY WARNING):** यदि आप या आपके पास कोई व्यक्ति सीने में दर्द, सांस लेने में कठिनाई, "
    "अचानक सुन्नपन या कमज़ोरी, दौरा (सीज़र) या अनियंत्रित रक्तस्राव जैसे गंभीर लक्षण महसूस कर रहा है, तो कृपया तुरंत "
    "आपातकालीन सेवाओं को कॉल करें (भारत में 112, अमेरिका में 911, यूके में 999) या नज़दीकी अस्पताल के आपातकालीन विभाग में जाएँ।"
)
_HI_CRISIS = (
    "🚨 **आपातकालीन चेतावनी (EMERGENCY WARNING):** मुझे बहुत खेद है कि आप इस दौर से गुज़र रहे हैं। आपको इसका सामना अकेले नहीं करना है।\n\n"
    "यदि आप इन विचारों पर अमल कर सकते हैं या तुरंत ख़तरे में हैं, तो कृपया अभी अपने स्थानीय आपातकालीन नंबर पर कॉल करें "
    "(भारत में 112, अमेरिका में 911, यूके में 999)।\n\n"
    "आप किसी से तुरंत बात भी कर सकते हैं: **भारत:** Tele-MANAS 14416 या 1-800-891-4416; **अमेरिका:** 988 पर कॉल या टेक्स्ट करें; "
    "अन्य देशों के लिए [https://findahelpline.com](https://findahelpline.com) देखें।"
)
_ES_MEDICAL = (
    "🚨 **ADVERTENCIA DE EMERGENCIA:** Si tú o alguien cerca de ti presenta síntomas graves como dolor de pecho, dificultad para "
    "respirar, entumecimiento o debilidad repentinos, una convulsión o una hemorragia incontrolable, llama de inmediato a los "
    "servicios de emergencia (112 en España y la UE, 911 en EE. UU. y México) o acude a urgencias del hospital más cercano."
)
_ES_CRISIS = (
    "🚨 **ADVERTENCIA DE EMERGENCIA:** Lamento mucho que estés pasando por esto. No tienes que afrontarlo solo/a.\n\n"
    "Si podrías actuar según estos pensamientos o estás en peligro inmediato, llama ahora a tu número de emergencias local "
    "(112 en España, 911 en EE. UU. y México).\n\n"
    "También puedes hablar con alguien ahora mismo: **España:** línea 024; **EE. UU.:** llama o envía un mensaje al 988; "
    "en otros lugares consulta [https://findahelpline.com](https://findahelpline.com)."
)
_FR_MEDICAL = (
    "🚨 **ALERTE D'URGENCE :** Si vous ou une personne près de vous présentez des symptômes graves (douleur thoracique, difficulté "
    "à respirer, engourdissement ou faiblesse soudains, convulsions, saignement abondant), appelez immédiatement les secours "
    "(15 ou 112 en France, 911 aux États-Unis) ou rendez-vous aux urgences les plus proches."
)
_FR_CRISIS = (
    "🚨 **ALERTE D'URGENCE :** Je suis sincèrement désolé que vous traversiez cela. Vous n'avez pas à y faire face seul(e).\n\n"
    "Si vous risquez de passer à l'acte ou si vous êtes en danger immédiat, appelez dès maintenant votre numéro d'urgence local "
    "(112 ou 15 en France, 911 aux États-Unis).\n\n"
    "Vous pouvez aussi parler à quelqu'un tout de suite : **France :** 3114 (numéro national de prévention du suicide) ; "
    "**États-Unis :** appelez ou envoyez un SMS au 988 ; ailleurs, voir [https://findahelpline.com](https://findahelpline.com)."
)
_DE_MEDICAL = (
    "🚨 **NOTFALLWARNUNG:** Wenn Sie oder jemand in Ihrer Nähe schwere Symptome wie Brustschmerzen, Atemnot, plötzliche Taubheit "
    "oder Schwäche, einen Krampfanfall oder unstillbare Blutungen hat, rufen Sie sofort den Notruf (112 in Deutschland und der EU, "
    "911 in den USA) oder suchen Sie die nächste Notaufnahme auf."
)
_DE_CRISIS = (
    "🚨 **NOTFALLWARNUNG:** Es tut mir sehr leid, dass Sie das gerade durchmachen. Sie müssen das nicht allein durchstehen.\n\n"
    "Wenn Sie diese Gedanken in die Tat umsetzen könnten oder in unmittelbarer Gefahr sind, rufen Sie bitte jetzt den Notruf Ihres "
    "Landes an (112 in Deutschland, 911 in den USA).\n\n"
    "Sie können auch sofort mit jemandem sprechen: **Deutschland:** Telefonseelsorge 0800 111 0 111 oder 0800 111 0 222 (kostenlos); "
    "**USA:** Anruf oder SMS an 988; anderswo siehe [https://findahelpline.com](https://findahelpline.com)."
)

_BANNERS = {
    "English": (MEDICAL_EMERGENCY_RESPONSE, CRISIS_RESPONSE),
    "Hindi": (_HI_MEDICAL, _HI_CRISIS),
    "Spanish": (_ES_MEDICAL, _ES_CRISIS),
    "French": (_FR_MEDICAL, _FR_CRISIS),
    "German": (_DE_MEDICAL, _DE_CRISIS),
}
_LANGUAGE_ALIASES = {
    "english": "English", "en": "English", "hindi": "Hindi", "hi": "Hindi", "spanish": "Spanish", "es": "Spanish",
    "french": "French", "fr": "French", "german": "German", "de": "German",
}

def _normalize_language(language: Optional[str]) -> str:
    if not language:
        return "English"
    key = str(language).strip().lower().split("-")[0].split("_")[0]
    return _LANGUAGE_ALIASES.get(key, "English")

def get_emergency_response(kind: EmergencyKind = EmergencyKind.MEDICAL, language: Optional[str] = None) -> str:
    medical, crisis = _BANNERS[_normalize_language(language)]
    return crisis if kind == EmergencyKind.SELF_HARM else medical

EMERGENCY_RESPONSE = MEDICAL_EMERGENCY_RESPONSE

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
