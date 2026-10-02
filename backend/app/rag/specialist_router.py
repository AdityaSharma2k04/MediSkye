import re
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.models import Specialist
from app.core.config import settings

# Mapping of clinical specialty categories to plain-language descriptions and matched flag patterns
SPECIALTY_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "Cardiology": {
        "title": "A cardiologist",
        "description": "for heart & cholesterol findings",
        "keywords": [
            "troponin", "ck-mb", "bnp", "lipid", "cholesterol", "triglycerides",
            "ldl", "hdl", "apolipoprotein", "blood pressure", "heart rate",
            "arrhythmia", "ecg", "echocardiogram", "cardiac"
        ],
    },
    "Endocrinology": {
        "title": "An endocrinologist",
        "description": "for blood sugar & diabetes",
        "keywords": [
            "hba1c", "glucose", "fasting blood sugar", "fbs", "thyroid", "tsh",
            "t3", "t4", "insulin", "cortisol", "diabetes", "hormone",
            "testosterone", "estrogen", "vitamin d", "calcium", "pth"
        ],
    },
    "Nephrology": {
        "title": "A nephrologist",
        "description": "for kidney function",
        "keywords": [
            "creatinine", "bun", "egfr", "urea", "proteinuria", "urinalysis",
            "sodium", "potassium", "microalbumin", "kidney"
        ],
    },
    "Hematology": {
        "title": "A hematologist",
        "description": "for blood & cell count findings",
        "keywords": [
            "hemoglobin", "wbc", "platelets", "rbc", "ferritin", "iron",
            "hematocrit", "mcv", "mch", "leukocyte", "anemia"
        ],
    },
    "Hepatology": {
        "title": "A gastroenterologist or hepatologist",
        "description": "for liver & metabolic findings",
        "keywords": [
            "alt", "ast", "sgpt", "sgot", "bilirubin", "alp", "albumin",
            "ggt", "liver", "hepatic"
        ],
    },
}

PLACEHOLDER_CONTACT_PATTERNS = [
    r"@mediskye\.org",
    r"555-\d{4}",
    r"555-\d{3}",
]


def is_placeholder_specialist(name: str, contact_info: Optional[str]) -> bool:
    """Check if specialist data contains placeholder names or contact details."""
    if contact_info:
        for pat in PLACEHOLDER_CONTACT_PATTERNS:
            if re.search(pat, contact_info, re.IGNORECASE):
                return True
    if name:
        for pat in PLACEHOLDER_CONTACT_PATTERNS:
            if re.search(pat, name, re.IGNORECASE):
                return True
    return False


def get_category_recommendations_for_flags(flags: List[str]) -> List[Dict[str, Any]]:
    """Derive generic clinical category recommendations from abnormal biomarker flags."""
    if not flags:
        return []

    flags_lower = {f.lower().strip() for f in flags}
    recommendations = []

    for specialty, cat in SPECIALTY_CATEGORIES.items():
        matched = set()
        for kw in cat["keywords"]:
            for fl in flags_lower:
                if kw in fl or fl in kw:
                    matched.add(fl)

        if matched:
            recommendations.append({
                "specialty": specialty,
                "title": cat["title"],
                "description": cat["description"],
                "matched_flags": sorted(list(matched)),
            })

    # Sort by number of matched flags descending
    recommendations.sort(key=lambda x: len(x["matched_flags"]), reverse=True)
    return recommendations


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
    Query specialists matching flags.
    - Excludes fake placeholder contacts (internal mock domains, generic phone patterns).
    - Gates real contacts behind settings.SHOW_SPECIALIST_CONTACTS (default False).
    - If no DB specialists exist, returns structured generic category recommendations.
    """
    if not flags:
        return []

    flags_lower = {f.lower().strip() for f in flags}

    # Query DB specialists if available
    db_specialists: List[Specialist] = []
    try:
        result = await db.execute(select(Specialist))
        all_specs = result.scalars().all()
        # Filter out fake rows
        db_specialists = [
            sp for sp in all_specs
            if not is_placeholder_specialist(sp.name, sp.contact_info)
        ]
    except Exception:
        db_specialists = []

    recommended = []
    for sp in db_specialists:
        sp_keywords = {k.lower() for k in sp.keywords} if sp.keywords else set()
        matched = flags_lower.intersection(sp_keywords)
        if matched:
            cat_info = SPECIALTY_CATEGORIES.get(sp.specialty, {
                "title": f"A specialist in {sp.specialty}",
                "description": f"for {sp.specialty.lower()} findings"
            })
            contact = sp.contact_info if settings.SHOW_SPECIALIST_CONTACTS else None
            recommended.append({
                "id": str(sp.id),
                "name": sp.name if settings.SHOW_SPECIALIST_CONTACTS else cat_info["title"],
                "specialty": sp.specialty,
                "title": cat_info["title"],
                "description": cat_info["description"],
                "contact_info": contact,
                "matched_flags": sorted(list(matched)),
            })

    if recommended:
        recommended.sort(key=lambda x: len(x["matched_flags"]), reverse=True)
        return recommended

    # Fallback to generic categories if no real DB specialists match
    generic_cats = get_category_recommendations_for_flags(flags)
    return [
        {
            "id": None,
            "name": cat["title"],
            "specialty": cat["specialty"],
            "title": cat["title"],
            "description": cat["description"],
            "contact_info": None,
            "matched_flags": cat["matched_flags"],
        }
        for cat in generic_cats
    ]
