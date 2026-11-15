import re
import logging
from typing import Optional, List, Dict, Any, Tuple, Union
from app.core.security import escape_xml_content

logger = logging.getLogger(__name__)

# Heuristic thresholds; a clinician must review any change.
LOW_ONLY_KEYS = {
    "ferritin", "vitamin_b12", "vitamin_d", "hemoglobin", "rbc", "wbc",
    "platelets", "folate", "serum_iron", "iron", "transferrin_saturation", "egfr", "hdl"
}

HIGH_ONLY_KEYS = {
    "creatinine", "bun", "uric_acid", "alt", "ast", "ggt", "alp", "bilirubin",
    "bilirubin_total", "bilirubin_direct", "glucose", "hba1c", "total_cholesterol",
    "ldl", "triglycerides", "non_hdl", "apob", "homocysteine", "crp", "hs_crp"
}

BOTH_SIDES_KEYS = {
    "tsh", "free_t4", "free_t3", "sodium", "potassium", "calcium",
    "magnesium", "phosphorus"
}

_RETEST_COMMON_STRING = (
    "If a clinician starts supplements or dietary changes for this marker, "
    "repeat testing is commonly scheduled after about 8–12 weeks."
)

_CLINICAL_FOLLOWUP_HINTS: Dict[str, Dict[str, Any]] = {
    "vitamin_b12": {
        "states": {"LOW", "LOW-NORMAL"},
        "context": (
            "Can be associated with reduced absorption or some medicines. "
            "A clinician may consider methylmalonic acid or homocysteine to assess functional B12 status."
        ),
        "symptoms": "fatigue, brain fog, tingling or numbness in hands or feet",
        "retest": True,
    },
    "ferritin": {
        "states": {"LOW", "LOW-NORMAL"},
        "context": (
            "Reflects iron stores. Clinicians often read it with hemoglobin, red-cell indices, "
            "serum iron, TIBC and transferrin saturation."
        ),
        "symptoms": "unusual tiredness, breathlessness or heavy legs on exertion, dizziness, hair shedding",
        "retest": True,
    },
    "vitamin_d": {
        "states": {"LOW", "LOW-NORMAL"},
        "context": (
            "Supports bone and muscle health. May be evaluated alongside calcium and parathyroid hormone."
        ),
        "symptoms": "bone or muscle aches, fatigue",
        "retest": True,
    },
    "hemoglobin": {
        "states": {"LOW", "LOW-NORMAL"},
        "context": (
            "Reflects oxygen-carrying capacity; usually read with iron studies and red-cell indices."
        ),
        "symptoms": "tiredness, dizziness, breathlessness",
        "retest": False,
    },
    "creatinine": {
        "states": {"HIGH", "HIGH-NORMAL"},
        "context": (
            "eGFR is calculated from creatinine and moves with it. Cystatin C is an option a clinician may consider."
        ),
        "symptoms": "none",
        "retest": False,
    },
    "ast": {
        "states": {"HIGH", "HIGH-NORMAL"},
        "context": (
            "Found in liver and muscle. A clinician may check creatine kinase and GGT."
        ),
        "symptoms": "none",
        "retest": False,
    },
    "tsh": {
        "states": {"HIGH", "LOW", "HIGH-NORMAL", "LOW-NORMAL"},
        "context": (
            "May be evaluated with free T4, free T3 and thyroid antibodies if clinically indicated."
        ),
        "symptoms": "temperature sensitivity, sluggishness or restlessness, hair or weight changes",
        "retest": False,
    },
    "ldl": {
        "states": {"HIGH", "HIGH-NORMAL"},
        "context": (
            "Interpreted with blood pressure, family history and blood sugar markers. "
            "Some clinicians add ApoB or Lp(a) for a fuller picture."
        ),
        "symptoms": "none",
        "retest": False,
    },
    "total_cholesterol": {
        "states": {"HIGH", "HIGH-NORMAL"},
        "context": (
            "Interpreted with blood pressure, family history and blood sugar markers. "
            "Some clinicians add ApoB or Lp(a) for a fuller picture."
        ),
        "symptoms": "none",
        "retest": False,
    },
    "triglycerides": {
        "states": {"HIGH", "HIGH-NORMAL"},
        "context": (
            "Interpreted with blood pressure, family history and blood sugar markers. "
            "Some clinicians add ApoB or Lp(a) for a fuller picture."
        ),
        "symptoms": "none",
        "retest": False,
    },
    "glucose": {
        "states": {"HIGH", "HIGH-NORMAL"},
        "context": (
            "Fasting glucose is a single morning snapshot while HbA1c reflects roughly three months. "
            "Clinicians read both with symptoms and risk factors."
        ),
        "symptoms": "none",
        "retest": False,
    },
    "hba1c": {
        "states": {"HIGH", "HIGH-NORMAL"},
        "context": (
            "Fasting glucose is a single morning snapshot while HbA1c reflects roughly three months. "
            "Clinicians read both with symptoms and risk factors."
        ),
        "symptoms": "none",
        "retest": False,
    },
    "uric_acid": {
        "states": {"HIGH", "HIGH-NORMAL"},
        "context": "Can be influenced by kidney clearance, metabolic factors and some medicines.",
        "symptoms": "joint pain or swelling, especially in the big toe or ankle",
        "retest": False,
    },
}


def canonical_biomarker_key(name: str, allow_urinalysis: bool = False) -> Optional[str]:
    """
    Returns the normalized canonical key for a clinical biomarker name using
    ordered, case-insensitive regex rules with word boundaries.
    HbA1c & glycated hemoglobin are tested before hemoglobin;
    hb_electrophoresis is tested before hemoglobin.
    Returns None for unknown biomarker names (logged at debug level).
    """
    if not name or not isinstance(name, str):
        return None
    n = name.lower().strip()
    n_clean = re.sub(r'[\(\)\[\]:,/]', ' ', n)
    n_clean = re.sub(r'\s+', ' ', n_clean).strip()

    # 0a. Urine Albumin-to-Creatinine Ratio (MUST precede urinalysis exclusions and individual renal markers)
    if re.search(r'\b(?:albumin\s+(?:to\s+)?creatinine\s+ratio|uacr|urine\s+acr|acr)\b', n_clean):
        return "urine_acr"

    # 0b. Urinalysis Dipstick & Microscopy Exclusions / Mapping
    if not allow_urinalysis:
        if re.search(r'\b(?:leukocyte\s+esterase|leucocyte\s+esterase|pus\s+cells?|epithelial\s+cells?|urinary|urine(?!\s*acr|\s*albumin\s*(?:to|/)?\s*creatinine)|microalbumin|specific\s+gravity|urobilinogen|nitrites?|ketones?|casts|crystals|bacteria|yeast|mucus)\b', n_clean):
            return None
    else:
        if re.search(r'\b(?:urine\s+microalbumin|urinary\s+microalbumin|microalbumin\s*\(?urine\)?|microalbuminuria|microalbumin)\b', n_clean):
            return "urine_microalbumin"
        if re.search(r'\b(?:urine\s+creatinine|urinary\s+creatinine|creatinine\s*\(?urine\)?)\b', n_clean):
            return "urine_creatinine"
        if re.search(r'\b(?:urine\s+colou?r|urinary\s+colou?r|^colou?r$)\b', n_clean):
            return "urine_color"
        if re.search(r'\b(?:urine\s+appearance|urinary\s+appearance|^appearance$|clarity)\b', n_clean):
            return "urine_appearance"
        if re.search(r'\b(?:urine\s+specific\s+gravity|specific\s+gravity|sp\s*gr)\b', n_clean):
            return "urine_specific_gravity"
        if re.search(r'\b(?:urine\s+ph|urinary\s+ph|reaction\s*\(?ph\)?|^ph$)\b', n_clean):
            return "urine_ph"
        if re.search(r'\b(?:urine\s+ketones?|urinary\s+ketones?|^ketones?|ketone\s+bodies)\b', n_clean):
            return "urine_ketones"
        if re.search(r'\b(?:urine\s+urobilinogen|urinary\s+urobilinogen|urobilinogen)\b', n_clean):
            return "urine_urobilinogen"
        if re.search(r'\b(?:urine\s+nitrites?|urinary\s+nitrites?|nitrites?)\b', n_clean):
            return "urine_nitrite"
        if re.search(r'\b(?:leukocyte\s+esterase|leucocyte\s+esterase)\b', n_clean):
            return "urine_leukocyte_esterase"
        if re.search(r'\b(?:pus\s+cells?(?:\s*wbc)?|urine\s+pus\s+cells?|urine\s+wbc)\b', n_clean):
            return "urine_pus_cells"
        if re.search(r'\b(?:urine\s+epithelial\s+cells?|epithelial\s+cells?)\b', n_clean):
            return "urine_epithelial_cells"
        if re.search(r'\b(?:urine\s+casts?|urinary\s+casts?|^casts?|hyaline\s+casts?|granular\s+casts?)\b', n_clean):
            return "urine_casts"
        if re.search(r'\b(?:urine\s+crystals?|urinary\s+crystals?|^crystals?|calcium\s+oxalate|uric\s+acid\s+crystals?)\b', n_clean):
            return "urine_crystals"
        if re.search(r'\b(?:urine\s+bacteria|urinary\s+bacteria|^bacteria$)\b', n_clean):
            return "urine_bacteria"
        if re.search(r'\b(?:urine\s+yeast|urinary\s+yeast|^yeast$)\b', n_clean):
            return "urine_yeast"
        if re.search(r'\b(?:urine\s+mucus|urinary\s+mucus|^mucus$)\b', n_clean):
            return "urine_mucus"
        if re.search(r'\b(?:urine\s+protein|urinary\s+protein|^protein$)\b', n_clean):
            return "urine_protein"
        if re.search(r'\b(?:urine\s+blood|urinary\s+blood|^blood$|occult\s+blood)\b', n_clean):
            return "urine_blood"
        if re.search(r'\b(?:urine\s+rbc|urinary\s+rbc|urine\s+red\s+blood\s+cells?)\b', n_clean):
            return "urine_rbc"
        if re.search(r'\b(?:urine\s+glucose|urinary\s+glucose|urine\s+sugar)\b', n_clean):
            return "urine_glucose"
        if re.search(r'\b(?:urine\s+bilirubin|urinary\s+bilirubin)\b', n_clean):
            return "urine_bilirubin"

    # 0c. Explicit Ratios (MUST precede individual lipid, renal, or liver markers so e.g. TC/HDL ratio never matches HDL)
    if re.search(r'\b(?:tc\s*/?\s*hdl(?:\s+ratio)?|total\s+cholesterol\s*/?\s*hdl(?:\s+ratio)?)\b', n_clean):
        return "tc_hdl_ratio"
    if re.search(r'\b(?:ldl\s*/?\s*hdl(?:\s+ratio)?)\b', n_clean):
        return "ldl_hdl_ratio"
    if re.search(r'\b(?:tg\s*/?\s*hdl(?:\s+ratio)?|triglycerides?\s*/?\s*hdl(?:\s+ratio)?)\b', n_clean):
        return "tg_hdl_ratio"
    if re.search(r'\b(?:bun\s*/?\s*creatinine(?:\s+ratio)?|urea\s*/?\s*creatinine(?:\s+ratio)?)\b', n_clean):
        return "bun_creatinine_ratio"
    if re.search(r'\b(?:ast\s*/?\s*alt(?:\s+ratio)?|sgot\s*/?\s*sgpt(?:\s+ratio)?|de\s+ritis(?:\s+ratio)?)\b', n_clean):
        return "ast_alt_ratio"
    if re.search(r'\b(?:a[\s/]*g\s+ratio|ag\s+ratio|albumin\s+globulin\s+ratio)\b', n_clean):
        return "ag_ratio"
    if re.search(r'\bratio\b', n_clean):
        return None

    # 1. HbA1c (MUST precede Hemoglobin)
    if re.search(r'\b(?:hba1c|glycated\s+h(?:a)?emoglobin|glycoh(?:a)?emoglobin|h(?:a)?emoglobin\s+a1c|a1c)\b', n_clean):
        return "hba1c"

    # 2. Hemoglobin variants & electrophoresis (MUST precede general Hemoglobin)
    if re.search(r'\b(?:hb\s*electrophoresis|h(?:a)?emoglobin\s*electrophoresis)\b', n_clean):
        return "hb_electrophoresis"
    if re.search(r'\b(?:hb\s*a2|h(?:a)?emoglobin\s*a2)\b', n_clean):
        return "hba2"
    if re.search(r'\b(?:hb\s*f|fetal\s*h(?:a)?emoglobin)\b', n_clean):
        return "hbf"

    # 3. RBC Indices MCHC, MCH, MCV (MUST precede general Hemoglobin)
    if re.search(r'\bmchc\b', n_clean):
        return "mchc"
    if re.search(r'\bmch\b', n_clean):
        return "mch"
    if re.search(r'\bmcv\b', n_clean):
        return "mcv"

    # 4. Hemoglobin (strict whole-word)
    if re.search(r'\b(?:h(?:a)?emoglobin(?:\s*\(?hb\)?)?|hb|hgb)\b', n_clean):
        return "hemoglobin"

    # 5. Non-HDL and VLDL (MUST precede HDL & Cholesterol)
    if re.search(r'\bnon[\s-]*hdl(?:\s+cholesterol)?\b', n_clean):
        return "non_hdl"
    if re.search(r'\bvldl(?:\s+cholesterol)?\b', n_clean):
        return "vldl"

    # 6. Hematocrit / PCV
    if re.search(r'\b(?:h(?:a)?ematocrit|pcv|packed\s+cell\s+volume|hct)\b', n_clean):
        return "hematocrit"

    # 7. WBC / TLC
    if re.search(r'\b(?:total\s+leukocyte\s+count|total\s+leucocyte\s+count|white\s+blood\s+cell(?:\s+count)?|white\s+blood\s+cells?|wbc(?:\s+count)?|leukocytes?|leucocytes?|tlc)\b', n_clean):
        return "wbc"

    # 8. RBC
    if re.search(r'\b(?:red\s+blood\s+cell(?:\s+count)?|red\s+blood\s+cells?|rbc(?:\s+count)?|erythrocytes?)\b', n_clean):
        return "rbc"

    # 9. MPV
    if re.search(r'\b(?:mean\s+platelet\s+volume|mpv)\b', n_clean):
        return "mpv"

    # 10. Platelets
    if re.search(r'\b(?:platelet\s+count|platelets?|plt)\b', n_clean):
        return "platelets"

    # 11. Ferritin
    if re.search(r'\b(?:serum\s+ferritin|ferritin)\b', n_clean):
        return "ferritin"

    # 12. Glucose (Fasting Plasma Glucose and general Glucose both resolve to 'glucose')
    if re.search(r'\b(?:fasting\s+plasma\s+glucose|fasting\s+blood\s+sugar|fasting\s+blood\s+glucose|fasting\s+glucose|fbs|fbg|glucose|blood\s+sugar|rbs|random\s+blood\s+sugar)\b', n_clean):
        return "glucose"

    # 12b. Urine albumin/creatinine ratio (MUST precede BUN and Creatinine, otherwise it is mis-keyed as serum creatinine)
    if re.search(r'\b(?:albumin\s+(?:to\s+)?creatinine\s+ratio|uacr|acr)\b', n_clean):
        return "urine_acr"

    # 13. BUN / Urea
    if re.search(r'\b(?:blood\s+urea\s+nitrogen|urea\s+nitrogen|bun)\b', n_clean):
        return "bun"

    # 14. Creatinine
    if re.search(r'\b(?:serum\s+creatinine|creatinine)\b', n_clean):
        return "creatinine"

    # 15. eGFR
    if re.search(r'\b(?:estimated\s+gfr|egfr|gfr)\b', n_clean):
        return "egfr"

    # 16. Uric Acid
    if re.search(r'\b(?:serum\s+uric\s+acid|uric\s+acid)\b', n_clean):
        return "uric_acid"

    # 17. ALT (SGPT)
    if re.search(r'\b(?:alanine\s+aminotransferase|alt\s*/?\s*sgpt|sgpt|alt)\b', n_clean):
        return "alt"

    # 18. AST (SGOT)
    if re.search(r'\b(?:aspartate\s+aminotransferase|ast\s*/?\s*sgot|sgot|ast)\b', n_clean):
        return "ast"

    # 19. Total Cholesterol
    if re.search(r'\b(?:total\s+cholesterol|cholesterol\s+total)\b', n_clean):
        return "total_cholesterol"

    # 20. HDL
    if re.search(r'\b(?:hdl\s+cholesterol|hdl)\b', n_clean):
        return "hdl"

    # 21. LDL
    if re.search(r'\b(?:ldl\s+cholesterol(?:\s*\(?calculated\)?)?|ldl)\b', n_clean):
        return "ldl"

    # 21b. Thyroid Autoantibodies (MUST precede Triglycerides to avoid \btg\b false positives)
    if re.search(r'\b(?:anti[\s-]*tpo|thyroid\s+peroxidase|tpo\s+antibod(?:y|ies)|microsomal\s+antibod(?:y|ies))\b', n_clean):
        return "anti_tpo"
    if re.search(r'\b(?:anti[\s-]*thyroglobulin|anti[\s-]*tg|thyroglobulin\s+antibod(?:y|ies)|atg)\b', n_clean):
        return "anti_tg"

    # 22. Triglycerides (requires word boundary, anti-tg exclusion safe)
    if re.search(r'\b(?:triglycerides?|(?<!anti\s)(?<!anti-)tg)\b', n_clean):
        return "triglycerides"

    # 23. Thyroid
    if re.search(r'\b(?:thyroid\s+stimulating\s+hormone|tsh)\b', n_clean):
        return "tsh"
    if re.search(r'\b(?:free\s+thyroxine|free\s+t4|ft4)\b', n_clean):
        return "free_t4"
    if re.search(r'\b(?:free\s+triiodothyronine|free\s+t3|ft3)\b', n_clean):
        return "free_t3"

    # 24. Vitamin B12
    if re.search(r'\b(?:vitamin\s+b12(?:\s*\(?cyanocobalamin\)?)?|b12|cyanocobalamin)\b', n_clean):
        return "vitamin_b12"

    # 25. Vitamin D
    if re.search(r'\b(?:25\s*-?\s*hydroxy\s+vitamin\s+d(?:\s*\(?total\)?)?|25\s*-?\s*oh\s+vitamin\s+d|vitamin\s+d3?|vit\s*d)\b', n_clean):
        return "vitamin_d"

    # 26. Other supported keys
    if re.search(r'\b(?:serum\s+iron|iron)\b', n_clean):
        return "serum_iron"
    if re.search(r'\b(?:total\s+iron\s+binding\s+capacity|tibc)\b', n_clean):
        return "tibc"
    if re.search(r'\b(?:transferrin\s+saturation|tsat)\b', n_clean):
        return "transferrin_saturation"
    if re.search(r'\bfolate\b', n_clean):
        return "folate"
    if re.search(r'\b(?:gamma\s*gt|ggt)\b', n_clean):
        return "ggt"
    if re.search(r'\b(?:alkaline\s+phosphatase|alp)\b', n_clean):
        return "alp"
    if re.search(r'\b(?:total\s+bilirubin|bilirubin)\b', n_clean):
        return "bilirubin"
    if re.search(r'\bapob\b', n_clean):
        return "apob"
    if re.search(r'\bhomocysteine\b', n_clean):
        return "homocysteine"
    if re.search(r'\b(?:hs\s*-?\s*crp|crp)\b', n_clean):
        return "crp"
    if re.search(r'\b(?:serum\s+sodium|sodium)\b', n_clean):
        return "sodium"
    if re.search(r'\b(?:serum\s+potassium|potassium)\b', n_clean):
        return "potassium"
    if re.search(r'\bcalcium\b', n_clean):
        return "calcium"
    if re.search(r'\bmagnesium\b', n_clean):
        return "magnesium"
    if re.search(r'\b(?:serum\s+albumin|albumin)\b', n_clean):
        return "albumin"
    if re.search(r'\bglobulin\b', n_clean):
        return "globulin"
    if re.search(r'\b(?:total\s+protein|serum\s+protein)\b', n_clean):
        return "total_protein"
    if re.search(r'\bphosphorus\b', n_clean):
        return "phosphorus"
    if re.search(r'\b(?:neutrophils?|polymorphs?)\b', n_clean):
        return "neutrophils"
    if re.search(r'\b(?:lymphocytes?|lymphs?)\b', n_clean):
        return "lymphocytes"
    if re.search(r'\b(?:monocytes?)\b', n_clean):
        return "monocytes"
    if re.search(r'\b(?:eosinophils?|eos)\b', n_clean):
        return "eosinophils"
    if re.search(r'\b(?:basophils?)\b', n_clean):
        return "basophils"
    if re.search(r'\b(?:rdw(?:\s*-\s*(?:cv|sd))?)\b', n_clean):
        return "rdw"
    if re.search(r'\b(?:blood\s+urea|urea)\b', n_clean):
        return "urea"
    if re.search(r'\b(?:direct\s+bilirubin|bilirubin\s+direct|conjugated\s+bilirubin)\b', n_clean):
        return "bilirubin_direct"
    if re.search(r'\b(?:indirect\s+bilirubin|bilirubin\s+indirect|unconjugated\s+bilirubin)\b', n_clean):
        return "bilirubin_indirect"
    if re.search(r'\b(?:chloride|cl-?)\b', n_clean):
        return "chloride"
    if re.search(r'\b(?:prostate\s+specific\s+antigen|psa)\b', n_clean):
        return "psa"
    if re.search(r'\b(?:troponin(?:\s*-\s*[it])?|trop\s*-\s*[it])\b', n_clean):
        return "troponin"
    if re.search(r'\b(?:bnp|nt\s*-?\s*probnp|pro\s*-?\s*bnp)\b', n_clean):
        return "bnp"
    if re.search(r'\b(?:pt[\s/]*inr|inr|prothrombin\s+time)\b', n_clean):
        return "inr"
    if re.search(r'\b(?:activated\s+partial\s+thromboplastin\s+time|aptt|ptt)\b', n_clean):
        return "aptt"
    if re.search(r'\b(?:lactate\s+dehydrogenase|ldh)\b', n_clean):
        return "ldh"
    if re.search(r'\b(?:amylase|serum\s+amylase)\b', n_clean):
        return "amylase"
    if re.search(r'\b(?:lipase|serum\s+lipase)\b', n_clean):
        return "lipase"
    if re.search(r'\b(?:creatine\s+kinase|ck|cpk)\b', n_clean):
        return "ck"

    logger.debug("Unknown biomarker name: %s", name)
    return None


def _normalize_numeric_string(s: str) -> str:
    """
    Normalizes numeric string with grouping commas and decimal separators:
    - Strips leading comparator symbols (<, >, <=, >=, ≤, ≥, =)
    - Handles standard thousands (150,000 or 4,500.50)
    - Handles Indian numbering (2,38,000 or 1,50,000 or 12,38,000.50)
    - Converts European decimal comma (3,9 -> 3.9, 12,5 -> 12.5)
    """
    s = re.sub(r'^[<>≤≥=\s]+', '', s).strip()
    if '.' in s and ',' in s:
        # Check which separator is decimal point
        if s.rfind(',') < s.rfind('.'):
            s = s.replace(',', '')
        else:
            s = s.replace('.', '').replace(',', '.')
    elif s.count(',') > 1:
        s = s.replace(',', '')
    elif ',' in s:
        if re.search(r',\d{3}$', s):
            s = s.replace(',', '')
        elif re.search(r',\d{1,2}$', s):
            s = s.replace(',', '.')
    return s


def parse_numeric_value(raw: Any) -> Optional[float]:
    """
    Parse a numeric value from string or float/int.
    Handles thousands comma (150,000 -> 150000, 4,500.50 -> 4500.5),
    Indian numbering (2,38,000 -> 238000), and decimal comma (3,9 -> 3.9).
    Skips qualitative values (Negative, Reactive, 1:160).
    Supports leading < or > comparators (e.g. '< 0.5' -> 0.5, '> 60' -> 60.0).
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return None
    # Skip qualitative values or ratios
    if re.search(r'\b(?:negative|positive|reactive|non-reactive|detected|not\s+detected|nil)\b', s, re.IGNORECASE):
        return None
    if ":" in s:
        return None

    s = _normalize_numeric_string(s)

    m = re.search(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', s)
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


def parse_reference_range(raw_range: Any) -> Optional[Dict[str, Any]]:
    """
    Parse a reference range string into structured bounds:
    Bounded: {'type': 'bounded', 'low': float, 'high': float}
    Upper-bounded: {'type': 'upper', 'high': float}
    Lower-bounded: {'type': 'lower', 'low': float}
    Supports hyphens, en-dash, em-dash, 'to', >=, <=, >, <, 'up to', 'above',
    comma decimal separators, and Indian/standard thousands grouping.
    Strips embedded units.
    """
    if raw_range is None:
        return None
    s = str(raw_range).strip()
    if not s:
        return None

    # Strip embedded units
    s_clean = re.sub(
        r'(?:/(?:cumm|[uµμ]l)|cells/[uµμ]l|\b(?:mg/dl|g/dl|mg/l|g/l|ng/ml|pg/ml|ug/l|µg/l|mcg/l|pmol/l|nmol/l|mmol/l|u/l|iu/l|miu/l|mu/l|uiu/ml|10\^?[36]/[uµμ]L|%|fl|pg|cumm|mm/hr|seconds?|sec)\b)',
        '', s, flags=re.IGNORECASE
    ).strip()

    # Strip qualitative/administrative prefixes e.g. "Normal:", "Target:", "Desirable:"
    s_clean = re.sub(r'^(?:normal|desirable|optimal|target|reference|ref|range)\s*[:\-]?\s*', '', s_clean, flags=re.IGNORECASE).strip()

    # 1. Bounded: 4.0 - 5.6, 0.70 – 1.25, 4.0 to 5.6, 1,50,000 - 4,50,000
    m_bounded = re.search(
        r'([0-9.,]+)\s*(?:-|–|—|−|\bto\b)\s*([0-9.,]+)',
        s_clean,
        re.IGNORECASE
    )
    if m_bounded:
        low = parse_numeric_value(_normalize_numeric_string(m_bounded.group(1)))
        high = parse_numeric_value(_normalize_numeric_string(m_bounded.group(2)))
        if low is not None and high is not None and low < high:
            return {"type": "bounded", "low": low, "high": high}

    # 2. Lower-bounded: >= 90, ≥ 40, > 60, above 40, greater than 60
    m_lower = re.search(r'(?:>=|≥|>|above|more\s+than|greater\s+than)\s*([0-9.,]+)', s_clean, re.IGNORECASE)
    if m_lower:
        val = parse_numeric_value(_normalize_numeric_string(m_lower.group(1)))
        if val is not None:
            return {"type": "lower", "low": val}

    # 3. Upper-bounded: < 200, <= 100, ≤ 150, up to 150, less than 200
    m_upper = re.search(r'(?:<=|≤|<|up\s+to|less\s+than)\s*([0-9.,]+)', s_clean, re.IGNORECASE)
    if m_upper:
        val = parse_numeric_value(_normalize_numeric_string(m_upper.group(1)))
        if val is not None:
            return {"type": "upper", "high": val}

    return None


def resolve_status(
    value: Any,
    interval: Any,
    stored_status: Optional[str] = None,
    test_name: str = "",
    status_mismatches: Optional[List[str]] = None,
) -> str:
    """
    Resolve biomarker status according to Section 4.4 policy:
    1. Normalize stored_status to Normal, Low, High, Critical, Borderline, or Abnormal.
    2. If valid normalized stored_status exists, keep it. If numeric check disagrees about
       in-range vs out-of-range, still keep stored_status, and append marker to status_mismatches.
    3. If no valid stored_status and both value and interval parse numerically, derive Low, High, or Normal.
    4. Otherwise return 'Unclassified'.
    """
    VALID_STATUSES = {
        "normal": "Normal",
        "low": "Low",
        "high": "High",
        "critical": "Critical",
        "borderline": "Borderline",
        "abnormal": "Abnormal",
    }
    norm_stored = None
    if stored_status and isinstance(stored_status, str):
        st_clean = stored_status.strip().lower()
        norm_stored = VALID_STATUSES.get(st_clean)

    num_val = parse_numeric_value(value)
    range_info = parse_reference_range(interval)

    derived = None
    if num_val is not None and range_info is not None:
        r_type = range_info["type"]
        if r_type == "bounded":
            if num_val < range_info["low"]:
                derived = "Low"
            elif num_val > range_info["high"]:
                derived = "High"
            else:
                derived = "Normal"
        elif r_type == "upper":
            if num_val > range_info["high"]:
                derived = "High"
            else:
                derived = "Normal"
        elif r_type == "lower":
            if num_val < range_info["low"]:
                derived = "Low"
            else:
                derived = "Normal"

    if norm_stored is not None:
        if derived is not None:
            # Check in-range vs out-of-range agreement
            stored_is_in_range = (norm_stored == "Normal")
            derived_is_in_range = (derived == "Normal")
            if stored_is_in_range != derived_is_in_range:
                if status_mismatches is not None and test_name:
                    status_mismatches.append(
                        f"{test_name}: stored status '{norm_stored}' differs from parsed numeric status '{derived}'"
                    )
        return norm_stored

    if derived is not None:
        return derived

    return "Unclassified"


def evaluate_near_boundary_flag(
    key: Optional[str],
    value: Any,
    interval: Any,
    unit: Optional[str] = None,
    status: str = "Normal",
) -> Optional[Tuple[str, int]]:
    """
    Evaluate near-boundary marker flag for Normal biomarkers.
    Returns (flag_label, percentage) e.g. ("LOW-NORMAL", 4) or None.
    """
    if status != "Normal" or not key:
        return None

    num_val = parse_numeric_value(value)
    range_info = parse_reference_range(interval)
    if num_val is None or range_info is None:
        return None

    norm_unit = (unit or "").strip().lower()
    r_type = range_info["type"]

    # Check allowed sides
    can_low = (key in LOW_ONLY_KEYS or key in BOTH_SIDES_KEYS)
    can_high = (key in HIGH_ONLY_KEYS or key in BOTH_SIDES_KEYS)

    if r_type == "bounded":
        low = range_info["low"]
        high = range_info["high"]
        if high <= low or num_val < low or num_val > high:
            return None
        position = (num_val - low) / (high - low)

        # 1. Low side check
        if can_low:
            # Check if key has absolute cap rule
            if key == "ferritin":
                if norm_unit in {"ng/ml", "ug/l", "µg/l", "mcg/l"}:
                    if position <= 0.15 and num_val < 50.0:
                        pct = int(round(position * 100))
                        return ("LOW-NORMAL", pct)
                else:
                    if position <= 0.10:
                        pct = int(round(position * 100))
                        return ("LOW-NORMAL", pct)
            elif key == "vitamin_b12":
                if norm_unit in {"pg/ml", "ng/l"}:
                    if position <= 0.15 and num_val < 350.0:
                        pct = int(round(position * 100))
                        return ("LOW-NORMAL", pct)
                else:
                    if position <= 0.10:
                        pct = int(round(position * 100))
                        return ("LOW-NORMAL", pct)
            elif key == "vitamin_d":
                if norm_unit in {"ng/ml"}:
                    if position <= 0.15 and num_val < 40.0:
                        pct = int(round(position * 100))
                        return ("LOW-NORMAL", pct)
                else:
                    if position <= 0.10:
                        pct = int(round(position * 100))
                        return ("LOW-NORMAL", pct)
            else:
                if position <= 0.15:
                    pct = int(round(position * 100))
                    return ("LOW-NORMAL", pct)

        # 2. High side check
        if can_high:
            if position >= 0.85:
                pct = int(round(position * 100))
                return ("HIGH-NORMAL", pct)

    elif r_type == "upper":
        high = range_info["high"]
        if can_high and 0.90 * high <= num_val <= high:
            pct = int(round((num_val / high) * 100))
            return ("HIGH-NORMAL", pct)

    elif r_type == "lower":
        low = range_info["low"]
        if can_low and low <= num_val <= 1.05 * low:
            pct = int(round((num_val / low) * 100))
            return ("LOW-NORMAL", pct)

    return None


def get_verified_absent_adjacent_tests(
    metric_names: List[str],
    raw_report_text: str = "",
) -> List[str]:
    """
    Check for verified absent adjacent tests when len(metrics) >= 5 and raw_report_text is non-empty.
    Synonym matching in raw_report_text suppresses candidates.
    Returns list of formatted strings e.g. '- Iron panel (Serum Iron, TIBC, Transferrin Saturation): not in requisition'.
    """
    if len(metric_names) < 5 or not raw_report_text or not raw_report_text.strip():
        return []

    combined_text = (raw_report_text + " " + " ".join(metric_names)).lower()
    keys_present = {canonical_biomarker_key(name) for name in metric_names if canonical_biomarker_key(name)}

    absent_lines = []

    # 1. Iron panel
    if "ferritin" in keys_present:
        synonyms = [
            r'\bserum\s+iron\b', r'\biron\b', r'\btibc\b',
            r'\btotal\s+iron\s+binding\s+capacity\b',
            r'\btransferrin\s+saturation\b', r'\btsat\b',
        ]
        any_found = any(re.search(pat, combined_text) for pat in synonyms)
        if not any_found:
            absent_lines.append("  - Iron panel (Serum Iron, TIBC, Transferrin Saturation): not in requisition")

    # 2. RBC indices
    if "hemoglobin" in keys_present:
        synonyms = [
            r'\bmcv\b', r'\bmean\s+corpuscular\s+volume\b',
            r'\bmch\b', r'\bmean\s+corpuscular\s+h(?:a)?emoglobin\b',
            r'\bmchc\b', r'\bmean\s+corpuscular\s+h(?:a)?emoglobin\s+concentration\b',
            r'\brdw\b', r'\bred\s+cell\s+distribution\s+width\b',
        ]
        any_found = any(re.search(pat, combined_text) for pat in synonyms)
        if not any_found:
            absent_lines.append("  - Red blood cell indices (MCV, MCH, MCHC, RDW): not in requisition")

    # 3. Thyroid hormones
    if "tsh" in keys_present:
        synonyms = [
            r'\bfree\s+t4\b', r'\bft4\b', r'\bfree\s+thyroxine\b',
            r'\bfree\s+t3\b', r'\bft3\b', r'\bfree\s+triiodothyronine\b',
        ]
        any_found = any(re.search(pat, combined_text) for pat in synonyms)
        if not any_found:
            absent_lines.append("  - Thyroid hormones (Free T4, Free T3): not in requisition")

    return absent_lines


def build_extracted_biomarkers_and_hints(
    active_docs_metrics: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
    raw_report_text: str = "",
) -> str:
    """
    Build deterministic <extracted_report_biomarkers count="N"> and <analysis_hints> blocks.
    Supports active_docs_metrics as a list of document dicts:
      [{"filename": ..., "metrics": [{"test": ..., "value": ..., "unit": ..., "range": ..., "status": ...}]}]
    OR as a flat list of metric dicts:
      [{"test": ..., "value": ..., ...}]
    Returns empty string if no metric rows.
    """
    if not active_docs_metrics:
        return ""

    # Flatten metric rows
    flat_metrics: List[Dict[str, Any]] = []
    if isinstance(active_docs_metrics, list):
        for item in active_docs_metrics:
            if isinstance(item, dict):
                if "metrics" in item and isinstance(item["metrics"], list):
                    flat_metrics.extend([m for m in item["metrics"] if isinstance(m, dict)])
                elif "test" in item:
                    flat_metrics.append(item)
    elif isinstance(active_docs_metrics, dict):
        if "metrics" in active_docs_metrics and isinstance(active_docs_metrics["metrics"], list):
            flat_metrics.extend([m for m in active_docs_metrics["metrics"] if isinstance(m, dict)])

    if not flat_metrics:
        return ""

    status_mismatches: List[str] = []
    unclassified_analytes: List[str] = []
    out_of_range_markers: List[str] = []
    high_markers: List[str] = []
    low_markers: List[str] = []
    other_flagged_markers: List[str] = []
    in_range_markers: List[str] = []
    near_boundaries: List[Dict[str, Any]] = []
    followup_hints: List[str] = []
    metric_lines: List[str] = []
    extracted_names: List[str] = []

    for m in flat_metrics:
        test_name = str(m.get("test") or "").strip()
        raw_val = m.get("value")
        val_str = "" if raw_val is None else str(raw_val).strip()
        unit_str = str(m.get("unit") or "").strip()
        range_str = str(m.get("range") or m.get("reference_range") or "").strip()
        stored_status = m.get("status")

        extracted_names.append(test_name)
        c_key = canonical_biomarker_key(test_name)

        final_status = resolve_status(
            value=val_str,
            interval=range_str,
            stored_status=stored_status,
            test_name=test_name,
            status_mismatches=status_mismatches,
        )

        # Deterministic status bucketing (matches Lab Metrics UI 100%)
        direction = None
        if final_status == "Normal":
            in_range_markers.append(test_name)
        elif final_status == "Unclassified":
            unclassified_analytes.append(test_name)
        else:
            out_of_range_markers.append(test_name)
            if final_status == "Low":
                direction = "Low"
            elif final_status == "High":
                direction = "High"
            else:
                num_v = parse_numeric_value(val_str)
                r_info = parse_reference_range(range_str)
                if num_v is not None and r_info is not None:
                    if r_info["type"] == "bounded":
                        if num_v < r_info["low"]:
                            direction = "Low"
                        elif num_v > r_info["high"]:
                            direction = "High"
                    elif r_info["type"] == "upper" and num_v > r_info["high"]:
                        direction = "High"
                    elif r_info["type"] == "lower" and num_v < r_info["low"]:
                        direction = "Low"

            if direction == "Low":
                low_markers.append(test_name)
            elif direction == "High" or final_status in {"High", "Critical"}:
                high_markers.append(test_name)
            else:
                other_flagged_markers.append(test_name)

        nb_flag = None
        if final_status == "Normal" and test_name not in [sm.split(":")[0] for sm in status_mismatches]:
            nb_flag = evaluate_near_boundary_flag(
                key=c_key,
                value=val_str,
                interval=range_str,
                unit=unit_str,
                status=final_status,
            )

        # Build analyte bullet line
        flag_str = ""
        if nb_flag:
            flag_label, pct = nb_flag
            flag_str = f" [Flag: {flag_label}, {pct}% of range]"
            near_boundaries.append({
                "test": test_name,
                "label": flag_label,
                "pct": pct,
                "range": range_str,
                "unit": unit_str,
            })

        ref_part = f" (Reference: {escape_xml_content(range_str)})" if range_str else ""
        unit_part = f" {escape_xml_content(unit_str)}" if unit_str else ""
        metric_lines.append(
            f"  - {escape_xml_content(test_name)}: {escape_xml_content(val_str)}{unit_part}{ref_part} [Status: {escape_xml_content(final_status)}]{flag_str}"
        )

        # Follow-up context check
        eff_state = nb_flag[0] if nb_flag else (direction.upper() if direction else final_status.upper())
        if c_key in _CLINICAL_FOLLOWUP_HINTS:
            hint_cfg = _CLINICAL_FOLLOWUP_HINTS[c_key]
            if eff_state in hint_cfg["states"]:
                retest_part = f" (Retest: {_RETEST_COMMON_STRING})" if hint_cfg["retest"] else ""
                symptoms_part = f" (Common symptoms: {hint_cfg['symptoms']})" if hint_cfg["symptoms"] != "none" else ""
                followup_hints.append(
                    f"  - {escape_xml_content(test_name)}: {hint_cfg['context']}{symptoms_part}{retest_part}"
                )

    # Verified absent adjacent tests
    absent_adjacent = get_verified_absent_adjacent_tests(extracted_names, raw_report_text)

    # Format XML output
    count = len(metric_lines)
    out_count = len(out_of_range_markers)
    in_count = len(in_range_markers)
    high_count = len(high_markers)
    low_count = len(low_markers)

    out_breakdown = f"High: {high_count}; Low: {low_count}"
    if other_flagged_markers:
        out_breakdown += f"; Other Flagged: {len(other_flagged_markers)}"

    xml_parts = [
        f'<extracted_report_biomarkers count="{count}">',
        "\n".join(metric_lines),
        '</extracted_report_biomarkers>',
        '<analysis_hints>',
        "status_summary:",
        f"  total_measured: {count}",
        f"  out_of_range_count: {out_count} ({out_breakdown})",
        f"  in_range_count: {in_count} (including {len(near_boundaries)} near-boundary)",
    ]

    if out_of_range_markers:
        xml_parts.append("  out_of_range_markers: " + " | ".join(escape_xml_content(x) for x in out_of_range_markers))
    else:
        xml_parts.append("  out_of_range_markers: none (all measured markers are within standard reference ranges)")

    if high_markers:
        xml_parts.append("  high_markers: " + " | ".join(escape_xml_content(x) for x in high_markers))
    if low_markers:
        xml_parts.append("  low_markers: " + " | ".join(escape_xml_content(x) for x in low_markers))
    if other_flagged_markers:
        xml_parts.append("  other_flagged_markers: " + " | ".join(escape_xml_content(x) for x in other_flagged_markers))

    if status_mismatches:
        xml_parts.append("\nstatus_mismatches:")
        for sm in status_mismatches:
            xml_parts.append(f"  - {escape_xml_content(sm)}")

    if unclassified_analytes:
        xml_parts.append("\nunclassified_analytes:")
        for ua in unclassified_analytes:
            xml_parts.append(f"  - {escape_xml_content(ua)}")

    xml_parts.append("\nnear_boundary_markers:")
    if near_boundaries:
        for nb in near_boundaries:
            u_suffix = f" {nb['unit']}" if nb['unit'] else ""
            xml_parts.append(
                f"  - {escape_xml_content(nb['test'])}: {nb['label']} ({nb['pct']}% of range; range {escape_xml_content(nb['range'])}{escape_xml_content(u_suffix)})"
            )
    else:
        xml_parts.append("  none")

    xml_parts.append("\nfollowup_context:")
    if followup_hints:
        xml_parts.extend(followup_hints)
    else:
        xml_parts.append("  none")

    xml_parts.append("\nverified_absent_adjacent_tests:")
    if absent_adjacent:
        xml_parts.extend(absent_adjacent)
    else:
        xml_parts.append("  none")

    xml_parts.append('</analysis_hints>')

    return "\n".join(xml_parts)

