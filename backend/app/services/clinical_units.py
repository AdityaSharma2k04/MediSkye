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


def parse_report_chronology(doc: Any) -> Optional[datetime]:
    """
    Parses specimen collection date (collected_at, format e.g. "24 Oct 2026") into a datetime.
    Supports Document ORM instances, dictionaries, or date strings.
    Falls back to created_at if collected_at is missing or unparseable.
    """
    if doc is None:
        return None

    # Handle string directly
    if isinstance(doc, str):
        col_str = doc.strip()
    elif isinstance(doc, dict):
        col_str = doc.get("collected_at")
    else:
        col_str = getattr(doc, "collected_at", None)

    if col_str and isinstance(col_str, str):
        col_str = col_str.strip()
        date_formats = (
            "%d %b %Y",
            "%d %B %Y",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y-%m-%d %H:%M:%S",
        )
        for fmt in date_formats:
            try:
                dt = datetime.strptime(col_str, fmt)
                return dt
            except ValueError:
                continue

    # Fallback to created_at
    created_at = None
    if isinstance(doc, dict):
        created_at = doc.get("created_at")
    elif not isinstance(doc, str):
        created_at = getattr(doc, "created_at", None)

    if isinstance(created_at, datetime):
        return created_at.replace(tzinfo=None) if created_at.tzinfo else created_at
    if isinstance(created_at, str):
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return dt.replace(tzinfo=None)
        except Exception:
            pass

    return None


def canonical_biomarker_key(name: str) -> str:
    """
    Returns a normalized key for matching clinical biomarkers across reports using whole-word regexes.
    Order matters:
      1. 'hba1c', 'glycated hemoglobin' -> 'hba1c'
      2. 'hemoglobin', \\bhb\\b, \\bhgb\\b -> 'hemoglobin'
      3. 'fasting plasma glucose' -> 'fasting_glucose'
      4. 'aspartate aminotransferase', \\bast\\b -> 'ast'
      5. Strict whole-word regexes for ALT, Vitamin D, B12, Ferritin, Creatinine, eGFR, BUN, Uric Acid, etc.
    """
    if not name:
        return ""
    n = name.lower().strip()
    # Normalize punctuation and brackets
    n_clean = re.sub(r'[\(\)\[\]:,/]', ' ', n)
    n_clean = re.sub(r'\s+', ' ', n_clean).strip()

    # 1. HbA1c (MUST precede Hemoglobin)
    if re.search(r'\b(?:hba1c|glycated\s+hemoglobin|glycohemoglobin|hemoglobin\s+a1c|a1c)\b', n_clean):
        return "hba1c"

    # 2. Hemoglobin (strict whole-word)
    if re.search(r'\b(?:hemoglobin|hb|hgb)\b', n_clean):
        return "hemoglobin"

    # 3. Fasting Glucose (MUST precede general glucose)
    if re.search(r'\b(?:fasting\s+plasma\s+glucose|fasting\s+blood\s+sugar|fasting\s+blood\s+glucose|fasting\s+glucose|fbs|fbg)\b', n_clean):
        return "fasting_glucose"

    # 4. AST (strict whole-word, never matches 'fasting')
    if re.search(r'\b(?:aspartate\s+aminotransferase|ast|sgot)\b', n_clean):
        return "ast"

    # 5. ALT
    if re.search(r'\b(?:alanine\s+aminotransferase|alt|sgpt)\b', n_clean):
        return "alt"

    # 6. Vitamin D (strict whole-word, e.g. 'Vit D', '25-OH Vitamin D')
    if re.search(r'\b(?:25\s*-?\s*oh\s+vitamin\s+d|vitamin\s+d3?|vit\s+d3?|25\s*-?\s*hydroxy\s*vitamin\s+d|calcidiol|25\s*-?\s*oh\s*-?\s*d)\b', n_clean):
        return "vitamin_d"

    # 7. Vitamin B12
    if re.search(r'\b(?:vitamin\s+b12|vit\s+b12|b12|cobalamin|cyanocobalamin)\b', n_clean):
        return "vitamin_b12"

    # 8. Ferritin
    if re.search(r'\b(?:serum\s+ferritin|ferritin)\b', n_clean):
        return "ferritin"

    # 9. Creatinine
    if re.search(r'\b(?:serum\s+creatinine|creatinine)\b', n_clean):
        return "creatinine"

    # 10. eGFR
    if re.search(r'\b(?:estimated\s+gfr|egfr|gfr)\b', n_clean):
        return "egfr"

    # 11. BUN
    if re.search(r'\b(?:blood\s+urea\s+nitrogen|bun|urea\s+nitrogen)\b', n_clean):
        return "bun"

    # 12. Uric Acid
    if re.search(r'\b(?:serum\s+uric\s+acid|uric\s+acid|urate)\b', n_clean):
        return "uric_acid"

    # 13. Platelets
    if re.search(r'\b(?:platelet\s+count|platelets?|plt)\b', n_clean):
        return "platelets"

    # 14. WBC
    if re.search(r'\b(?:white\s+blood\s+cell(?:\s+count)?|white\s+blood\s+cells?|wbc(?:\s+count)?|leukocytes?)\b', n_clean):
        return "wbc"

    # 15. RBC
    if re.search(r'\b(?:red\s+blood\s+cell(?:\s+count)?|red\s+blood\s+cells?|rbc(?:\s+count)?|erythrocytes?)\b', n_clean):
        return "rbc"

    # 16. Glucose (general)
    if re.search(r'\b(?:glucose|blood\s+sugar|rbs)\b', n_clean):
        return "glucose"

    # 17. LDL
    if re.search(r'\b(?:ldl\s+cholesterol|ldl(?:\s*-\s*c)?)\b', n_clean):
        return "ldl"

    # 18. HDL
    if re.search(r'\b(?:hdl\s+cholesterol|hdl(?:\s*-\s*c)?)\b', n_clean):
        return "hdl"

    # 19. Triglycerides
    if re.search(r'\b(?:triglycerides?|tg)\b', n_clean):
        return "triglycerides"

    # 20. Cholesterol
    if re.search(r'\b(?:total\s+cholesterol|cholesterol)\b', n_clean):
        return "cholesterol"

    # Fallback normalization
    for prefix in ["serum ", "total ", "blood "]:
        if n_clean.startswith(prefix) and n_clean != "total cholesterol":
            n_clean = n_clean[len(prefix):].strip()

    return re.sub(r'\s+', '_', n_clean)


# Backward-compatible alias
canonical_biomarker_name = canonical_biomarker_key


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


ALLOWED_DELTA_DROP_KEYS = {
    "hemoglobin",
    "ferritin",
    "vitamin_b12",
    "vitamin_d",
    "platelets",
    "rbc",
    "wbc",
    "egfr",
}


def compute_biomarker_delta(
    current_val_str: str,
    prev_val_str: str,
    status: str = "Normal",
    unit: str = "",
    canonical_key: str = "",
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Computes absolute and percentage delta between current and previous values.
    Returns (delta_abs, delta_pct, delta_alert).

    Delta Check Rule:
      Only set delta_alert on a Normal biomarker if:
        1. delta_pct <= -10.0 (a drop, never a rise).
        2. The canonical key is in {"hemoglobin", "ferritin", "vitamin_b12", "vitamin_d", "platelets", "rbc", "wbc", "egfr"}.
      Never flag a rise in Vitamin D, B12, or Ferritin as "abnormal".
      Never flag a drop in Uric Acid or LDL as "Notable Drop".
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
        # Only set delta_alert on a Normal biomarker if delta_pct <= -10.0 (a drop, never a rise)
        # AND the canonical key is in ALLOWED_DELTA_DROP_KEYS.
        if pct <= -10.0 and canonical_key in ALLOWED_DELTA_DROP_KEYS:
            delta_alert = f"Notable Drop ({pct:+.1f}%)"

    return (delta_abs_formatted, delta_pct, delta_alert)

