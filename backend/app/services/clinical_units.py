import re
from datetime import datetime, UTC
from typing import Optional, Dict, Any, Tuple


def normalize_clinical_unit(unit: Optional[str]) -> str:
    """
    Deterministic normalizer for clinical laboratory units.
    Replaces ASCII/caret representations with Unicode clinical superscripts:
      - 103/µL, 103/μL, 10^3/uL, 10^3/µL -> 10³/µL
      - 106/µL, 106/μL, 10^6/uL -> 10⁶/µL
      - mL/min/1.73m2, mL/min/1.73m^2 -> mL/min/1.73m²
    """
    if not unit or not isinstance(unit, str):
        return ""
    u = unit.strip()

    # 1. 10^3 / uL or 103/uL variants -> 10³/µL
    u = re.sub(r'10\^?3\s*/\s*[uµμ]L', '10³/µL', u, flags=re.IGNORECASE)

    # 2. 10^6 / uL or 106/uL variants -> 10⁶/µL
    u = re.sub(r'10\^?6\s*/\s*[uµμ]L', '10⁶/µL', u, flags=re.IGNORECASE)

    # 3. mL/min/1.73m2 variants -> mL/min/1.73m²
    u = re.sub(r'mL/min/1\.73\s*m\^?2', 'mL/min/1.73m²', u, flags=re.IGNORECASE)

    # 4. Standardize micro-litre variants if bare uL
    u = re.sub(r'(?<![a-zA-Z0-9])uL\b', 'µL', u)
    u = re.sub(r'(?<![a-zA-Z0-9])ug\b', 'µg', u)
    u = re.sub(r'(?<![a-zA-Z0-9])umol\b', 'µmol', u)

    return u


def extract_specimen_collection_date(text: Optional[str]) -> Optional[str]:
    """
    Extracts the specimen collection date from clinical document text or header.
    Matches formats like 'SAMPLE COLLECTED: 24 Oct 2026', 'Date: 24 Apr 2027',
    'Collection Date: 2026-10-15', or explicit date stamps.
    Standardizes output to 'DD Mon YYYY' format (e.g., '24 Oct 2026').
    """
    if not text or not isinstance(text, str):
        return None

    patterns = [
        r'(?:sample\s+collected|collection\s+date|date\s+of\s+collection|specimen\s+collected|collected\s+date|collected|date)\s*[:\-]?\s*([0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})',
        r'(?:sample\s+collected|collection\s+date|date\s+of\s+collection|specimen\s+collected|collected\s+date|collected|date)\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2})',
        r'(?:sample\s+collected|collection\s+date|date\s+of\s+collection|specimen\s+collected|collected\s+date|collected|date)\s*[:\-]?\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})',
        r'\b([0-9]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+[0-9]{4})\b',
    ]

    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            # Normalize ISO YYYY-MM-DD
            try:
                dt = datetime.strptime(raw, '%Y-%m-%d')
                return dt.strftime('%d %b %Y')
            except ValueError:
                pass
            # Normalize DD/MM/YYYY
            try:
                dt = datetime.strptime(raw, '%d/%m/%Y')
                return dt.strftime('%d %b %Y')
            except ValueError:
                pass
            return raw

    return None


def check_is_future_date(date_str: Optional[str]) -> bool:
    """
    Checks if a formatted date string represents a date in the future
    relative to today's UTC calendar date.
    """
    if not date_str:
        return False
    try:
        now_date = datetime.now(UTC).date()
        for fmt in ("%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%d %B %Y"):
            try:
                dt = datetime.strptime(date_str, fmt).date()
                return dt > now_date
            except ValueError:
                continue
    except Exception:
        pass
    return False


def canonical_biomarker_name(name: str) -> str:
    """
    Returns a normalized key for matching clinical biomarkers across reports.
    Handles clinical aliases, abbreviations, and parenthetical names:
      'Serum Creatinine' -> 'creatinine'
      'AST (SGOT)' -> 'ast'
      'ALT (SGPT)' -> 'alt'
      'Vitamin B12' -> 'vitamin_b12'
      '25-OH Vitamin D' -> 'vitamin_d'
      'Hemoglobin' -> 'hemoglobin'
    """
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r'[\(\)\[\]]', ' ', n)
    for prefix in ["serum ", "total ", "blood "]:
        if n.startswith(prefix) and n != "total cholesterol":
            n = n[len(prefix):].strip()

    if "creatinine" in n:
        return "creatinine"
    if "b12" in n or "cobalamin" in n:
        return "vitamin_b12"
    if "vitamin d" in n or "25-oh" in n:
        return "vitamin_d"
    if "ferritin" in n:
        return "ferritin"
    if "hemoglobin" in n or n in ("hb", "hgb"):
        return "hemoglobin"
    if "ast" in n or "sgot" in n:
        return "ast"
    if "alt" in n or "sgpt" in n:
        return "alt"
    if "uric acid" in n or "urate" in n:
        return "uric_acid"
    if "egfr" in n:
        return "egfr"
    if "ldl" in n:
        return "ldl"
    if "hdl" in n:
        return "hdl"
    if "triglyceride" in n:
        return "triglycerides"
    if "cholesterol" in n:
        return "cholesterol"
    if "wbc" in n or "white blood" in n:
        return "wbc"
    if "platelet" in n:
        return "platelets"
    return re.sub(r'\s+', '_', n)


def _parse_first_float(s: Any) -> Optional[float]:
    if s is None:
        return None
    m = re.search(r'[-+]?[0-9]*\.?[0-9]+', str(s))
    if m:
        try:
            return float(m.group(0))
        except ValueError:
            return None
    return None


def compute_biomarker_delta(
    current_val_str: str,
    prev_val_str: str,
    status: str = "Normal",
    unit: str = ""
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Computes absolute and percentage delta between current and previous values.
    Returns (delta_abs, delta_pct, delta_alert).

    Delta Check Rule:
      If a biomarker's status is 'Normal' (or within normal limits) but it shifted
      by >= 10% toward a clinical boundary (such as Hemoglobin dropping -11.7%
      from 15.4 to 13.6 g/dL), sets delta_alert = 'Notable Drop (-11.7%)' or 'Notable Rise'.
    """
    c_val = _parse_first_float(current_val_str)
    p_val = _parse_first_float(prev_val_str)

    if c_val is None or p_val is None or p_val == 0:
        return (None, None, None)

    diff = c_val - p_val
    pct = (diff / p_val) * 100.0

    # Format abs diff: e.g. -1.8, +17, +1.8
    if diff == int(diff):
        delta_abs = f"{diff:+.0f}"
    else:
        delta_abs = f"{diff:+.2f}".rstrip('0').rstrip('.')
    if unit:
        delta_abs_formatted = f"{delta_abs} {unit}"
    else:
        delta_abs_formatted = delta_abs

    delta_pct = f"{pct:+.1f}%"

    # Delta Check Alert Rule
    delta_alert = None
    status_clean = (status or "").strip().lower()
    if status_clean in ("normal", "within normal limits", "in-range", ""):
        if pct <= -10.0:
            delta_alert = f"Notable Drop ({pct:+.1f}%)"
        elif pct >= 10.0:
            delta_alert = f"Notable Rise ({pct:+.1f}%)"

    return (delta_abs_formatted, delta_pct, delta_alert)

