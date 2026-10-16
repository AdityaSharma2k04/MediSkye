from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

SPECIALIST_MAP = {
    "hba1c": "Endocrinology",
    "glucose": "Endocrinology",
    "fasting blood sugar": "Endocrinology",
    "fbs": "Endocrinology",
    "thyroid": "Endocrinology",
    "tsh": "Endocrinology",
    "t3": "Endocrinology",
    "t4": "Endocrinology",
    "insulin": "Endocrinology",
    "cortisol": "Endocrinology",
    "diabetes": "Endocrinology",
    "hormone": "Endocrinology",
    "testosterone": "Endocrinology",
    "estrogen": "Endocrinology",
    "vitamin d": "Endocrinology",
    "calcium": "Endocrinology",
    "pth": "Endocrinology",

    "troponin": "Cardiology",
    "ck-mb": "Cardiology",
    "bnp": "Cardiology",
    "lipid": "Cardiology",
    "cholesterol": "Cardiology",
    "triglycerides": "Cardiology",
    "ldl": "Cardiology",
    "hdl": "Cardiology",
    "apolipoprotein": "Cardiology",
    "blood pressure": "Cardiology",
    "heart rate": "Cardiology",
    "arrhythmia": "Cardiology",
    "ecg": "Cardiology",
    "echocardiogram": "Cardiology",
    "cardiac": "Cardiology",

    "creatinine": "Nephrology",
    "bun": "Nephrology",
    "egfr": "Nephrology",
    "urea": "Nephrology",
    "proteinuria": "Nephrology",
    "urinalysis": "Nephrology",
    "sodium": "Nephrology",
    "potassium": "Nephrology",
    "microalbumin": "Nephrology",
    "kidney": "Nephrology",

    "hemoglobin": "Hematology",
    "wbc": "Hematology",
    "platelets": "Hematology",
    "rbc": "Hematology",
    "ferritin": "Hematology",
    "iron": "Hematology",
    "hematocrit": "Hematology",
    "mcv": "Hematology",
    "mch": "Hematology",
    "leukocyte": "Hematology",
    "anemia": "Hematology",

    "alt": "Hepatology",
    "ast": "Hepatology",
    "sgpt": "Hepatology",
    "sgot": "Hepatology",
    "bilirubin": "Hepatology",
    "alp": "Hepatology",
    "albumin": "Hepatology",
    "ggt": "Hepatology",
    "liver": "Hepatology",
    "hepatic": "Hepatology",
}

SPECIALTY_INFO = {
    "Cardiology": {"title": "A cardiologist", "description": "for heart & cholesterol findings"},
    "Endocrinology": {"title": "An endocrinologist", "description": "for blood sugar & diabetes"},
    "Nephrology": {"title": "A nephrologist", "description": "for kidney function"},
    "Hematology": {"title": "A hematologist", "description": "for blood & cell count findings"},
    "Hepatology": {"title": "A gastroenterologist or hepatologist", "description": "for liver & metabolic findings"},
}

def format_specialist_copy(recommendations: List[Dict[str, Any]]) -> str:
    """
    Format generic specialist recommendation text per the medical copy requirements.
    """
    if not recommendations:
        return ""

    lines = ["Based on these findings, you may want to consult:"]
    for rec in recommendations:
        lines.append(f"- {rec['title']} ({rec['description']})")

    lines.append("")
    lines.append("These are general recommendations, not referrals. Discuss with your primary care physician first.")
    return "\n".join(lines)


async def get_recommended_specialists(db: AsyncSession, flags: List[str]) -> List[Dict[str, Any]]:
    """
    Map abnormal flags to recommended specialists using a static map.
    Each flag maps to exactly ONE specialty via direct key lookup.
    """
    if not flags:
        return []

    specialty_to_flags: Dict[str, set] = {}

    for fl in flags:
        key = fl.lower().strip()
        specialty = SPECIALIST_MAP.get(key)
        if specialty:
            specialty_to_flags.setdefault(specialty, set()).add(key)

    recommendations = []
    for specialty, matched in specialty_to_flags.items():
        info = SPECIALTY_INFO[specialty]
        recommendations.append({
            "id": None,
            "name": info["title"],
            "specialty": specialty,
            "title": info["title"],
            "description": info["description"],
            "contact_info": None,
            "matched_flags": sorted(list(matched)),
        })

    recommendations.sort(key=lambda x: len(x["matched_flags"]), reverse=True)
    return recommendations
