import re
from datetime import UTC, datetime
from typing import Any


def normalize_clinical_unit(unit: str | None) -> str:
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

    # 5. Indian and legacy clinical laboratory unit normalizations
    u = re.sub(r'\b(?:mill|million|mil)\s*/\s*(?:cu\.?\s*mm|cumm)\b', '10⁶/µL', u, flags=re.IGNORECASE)
    u = re.sub(r'\b(?:thou|thousand)\s*/\s*(?:cu\.?\s*mm|cumm)\b', '10³/µL', u, flags=re.IGNORECASE)
    u = re.sub(r'\bgm\s*%', 'g/dL', u, flags=re.IGNORECASE)
    u = re.sub(r'\bgm\s*/\s*dl\b', 'g/dL', u, flags=re.IGNORECASE)
    u = re.sub(r'\bg\s*/\s*dl\b', 'g/dL', u, flags=re.IGNORECASE)
    u = re.sub(r'\bmg\s*/\s*dl\b', 'mg/dL', u, flags=re.IGNORECASE)

    return u


def extract_specimen_collection_date(text: str | None) -> str | None:
    """
    Extracts the specimen collection date from clinical document text or header.
    Matches formats like 'SAMPLE COLLECTED: 24 Oct 2026', 'Date: 24 Apr 2027',
    'Collection Date: 2026-10-15', 'Collected On\n| 08-Nov-2026 07:42',
    'Collected On\n 09-Nov-2026 08:05', or explicit date stamps.
    Standardizes output to 'DD Mon YYYY' format (e.g., '24 Oct 2026').
    """
    if not text or not isinstance(text, str):
        return None

    labels = (
        r'(?:sample\s+collected|collection\s+date|date\s+of\s+collection|'
        r'specimen\s+collected|collected\s+date|collected\s+on|received\s+on|'
        r'reported\s+on|collected|date)'
    )
    sep = r'[\s|:|\-\n]{1,30}'

    patterns = [
        # Label + DD-Mon-YYYY or DD Mon YYYY (e.g. 08-Nov-2026, 24 Oct 2026)
        rf'{labels}{sep}([0-9]{{1,2}}[-\s]+[A-Za-z]{{3,9}}[-\s]+[0-9]{{4}})',
        # Label + YYYY-MM-DD
        rf'{labels}{sep}([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})',
        # Label + DD/MM/YYYY
        rf'{labels}{sep}([0-9]{{1,2}}/[0-9]{{1,2}}/[0-9]{{4}})',
        # Label + Mon DD, YYYY or Mon DD YYYY (e.g. Nov 08, 2026)
        rf'{labels}{sep}([A-Za-z]{{3,9}}[-\s]+[0-9]{{1,2}},?[-\s]+[0-9]{{4}})',
        # Standalone DD Mon YYYY / DD-Mon-YYYY without label
        r'\b([0-9]{1,2}[-\s]+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-\s]+[0-9]{4})\b',
    ]

    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            # Normalize to DD Mon YYYY
            for fmt in (
                "%d-%b-%Y", "%d %b %Y", "%d-%B-%Y", "%d %B %Y",
                "%Y-%m-%d", "%d/%m/%Y",
                "%b %d, %Y", "%b %d %Y", "%B %d, %Y", "%B %d %Y",
            ):
                try:
                    dt = datetime.strptime(raw, fmt)
                    return dt.strftime('%d %b %Y')
                except ValueError:
                    continue
            return raw

    return None


def check_is_future_date(date_str: str | None) -> bool:
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


def parse_report_chronology(doc: Any) -> datetime | None:
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
            "%B %d, %Y",
            "%b %d, %Y",
            "%B %d %Y",
            "%b %d %Y",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%b-%Y",
            "%d-%B-%Y",
            "%d-%m-%Y",
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


def canonical_biomarker_key(name: str, allow_urinalysis: bool = False) -> str:
    """
    Returns a normalized key for matching clinical biomarkers across reports using whole-word regexes.
    Order matters:
      1. 'hba1c', 'glycated hemoglobin' -> 'hba1c'
      2. 'non-hdl', 'vldl' -> 'non_hdl', 'vldl' (MUST precede HDL & Cholesterol)
      3. 'mchc', 'mch', 'mcv' -> 'mchc', 'mch', 'mcv' (MUST precede Hemoglobin)
      4. 'hemoglobin', \\bhb\\b, \\bhgb\\b -> 'hemoglobin'
      5. 'hematocrit', 'pcv' -> 'hematocrit'
      6. 'wbc', 'tlc' -> 'wbc'
      7. 'fasting plasma glucose' -> 'fasting_glucose'
      8. Strict whole-word regexes for AST, ALT, ALP, GGT, Bilirubins, Proteins, Electrolytes, Thyroid, etc.
    """
    if not name:
        return ""
    if allow_urinalysis:
        from app.rag.biomarkers import canonical_biomarker_key as _rag_canonical_key
        r_key = _rag_canonical_key(name, allow_urinalysis=True)
        if r_key and r_key.startswith("urine_"):
            return r_key

    n = name.lower().strip()
    # Normalize punctuation and brackets
    n_clean = re.sub(r'[\(\)\[\]:,/]', ' ', n)
    n_clean = re.sub(r'\s+', ' ', n_clean).strip()

    # 0a. Urine Albumin-to-Creatinine Ratio (MUST precede urinalysis exclusions and individual renal markers)
    if re.search(r'\b(?:albumin\s+(?:to\s+)?creatinine\s+ratio|uacr|acr)\b', n_clean):
        return "urine_acr"

    # 0b. Urinalysis Dipstick & Microscopy Exclusions (return "" so they NEVER collide with blood markers like WBC, RBC or Albumin)
    if re.search(r'\b(?:leukocyte\s+esterase|leucocyte\s+esterase|pus\s+cells?|epithelial\s+cells?|urinary|urine(?!\s*acr|\s*albumin\s*(?:to|/)?\s*creatinine)|microalbumin|specific\s+gravity|urobilinogen|nitrites?|ketones?|casts|crystals|bacteria|yeast|mucus)\b', n_clean):
        return ""

    # 0c. Explicit Ratios (MUST precede individual lipid, renal, or liver markers)
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
        return ""

    # 1. HbA1c (MUST precede Hemoglobin)
    if re.search(r'\b(?:hba1c|glycated\s+hemoglobin|glycohemoglobin|hemoglobin\s+a1c|a1c)\b', n_clean):
        return "hba1c"

    # 2. Non-HDL and VLDL (MUST precede HDL & Cholesterol)
    if re.search(r'\bnon[\s-]*hdl(?:\s+cholesterol)?\b', n_clean):
        return "non_hdl"
    if re.search(r'\bvldl(?:\s+cholesterol)?\b', n_clean):
        return "vldl"

    # 3. RBC Indices MCHC, MCH, MCV (MUST precede Hemoglobin so they never match Hb)
    if re.search(r'\bmchc\b', n_clean):
        return "mchc"
    if re.search(r'\bmch\b', n_clean):
        return "mch"
    if re.search(r'\bmcv\b', n_clean):
        return "mcv"

    # 3b. Hemoglobin variants & electrophoresis (MUST precede general Hemoglobin)
    if re.search(r'\b(?:hb\s*electrophoresis|hemoglobin\s*electrophoresis)\b', n_clean):
        return "hb_electrophoresis"
    if re.search(r'\b(?:hb\s*a2|hemoglobin\s*a2)\b', n_clean):
        return "hba2"
    if re.search(r'\b(?:hb\s*f|fetal\s*hemoglobin)\b', n_clean):
        return "hbf"

    # 4. Hemoglobin (strict whole-word)
    if re.search(r'\b(?:hemoglobin|hb|hgb)\b', n_clean):
        return "hemoglobin"

    # 5. Hematocrit / Packed Cell Volume (PCV)
    if re.search(r'\b(?:hematocrit|pcv|packed\s+cell\s+volume|hct)\b', n_clean):
        return "hematocrit"

    # 6. WBC / TLC (Total Leucocyte Count)
    if re.search(r'\b(?:white\s+blood\s+cell(?:\s+count)?|white\s+blood\s+cells?|wbc(?:\s+count)?|leukocytes?|leucocytes?|tlc|total\s+leucocyte\s+count|total\s+leukocyte\s+count)\b', n_clean):
        return "wbc"

    # 7. RBC
    if re.search(r'\b(?:red\s+blood\s+cell(?:\s+count)?|red\s+blood\s+cells?|rbc(?:\s+count)?|erythrocytes?)\b', n_clean):
        return "rbc"

    # 8. MPV (MUST precede Platelets)
    if re.search(r'\b(?:mean\s+platelet\s+volume|mpv)\b', n_clean):
        return "mpv"

    # 9. Platelets
    if re.search(r'\b(?:platelet\s+count|platelets?|plt)\b', n_clean):
        return "platelets"

    # 9. ESR
    if re.search(r'\b(?:erythrocyte\s+sedimentation\s+rate|esr)\b', n_clean):
        return "esr"

    # 10. CRP
    if re.search(r'\b(?:c\s*-?\s*reactive\s+protein|crp|hs\s*-?\s*crp)\b', n_clean):
        return "crp"

    # 11. Fasting Glucose (MUST precede general glucose, both resolve to 'glucose')
    if re.search(r'\b(?:fasting\s+plasma\s+glucose|fasting\s+blood\s+sugar|fasting\s+blood\s+glucose|fasting\s+glucose|fbs|fbg)\b', n_clean):
        return "glucose"

    # 12. General Glucose
    if re.search(r'\b(?:glucose|blood\s+sugar|rbs|random\s+blood\s+sugar)\b', n_clean):
        return "glucose"

    # 13. Thyroid: Free T3/T4 MUST precede total T3/T4
    if re.search(r'\b(?:free\s+triiodothyronine|free\s+t3|ft3)\b', n_clean):
        return "free_t3"
    if re.search(r'\b(?:free\s+thyroxine|free\s+t4|ft4)\b', n_clean):
        return "free_t4"
    if re.search(r'\b(?:thyroid\s+stimulating\s+hormone|tsh|thyrotropin)\b', n_clean):
        return "tsh"
    if re.search(r'\b(?:total\s+t3|t3|triiodothyronine)\b', n_clean):
        return "t3"
    if re.search(r'\b(?:total\s+t4|t4|thyroxine)\b', n_clean):
        return "t4"

    # 14. AST (strict whole-word, never matches 'fasting')
    if re.search(r'\b(?:aspartate\s+aminotransferase|ast|sgot)\b', n_clean):
        return "ast"

    # 15. ALT
    if re.search(r'\b(?:alanine\s+aminotransferase|alt|sgpt)\b', n_clean):
        return "alt"

    # 16. ALP & GGT
    if re.search(r'\b(?:alkaline\s+phosphatase|alp)\b', n_clean):
        return "alp"
    if re.search(r'\b(?:gamma\s*-?\s*glutamyl\s*trans(?:ferase|peptidase)|gamma\s*-?\s*gt|ggt)\b', n_clean):
        return "ggt"

    # 17. Bilirubin (Direct & Indirect MUST precede Total)
    if re.search(r'\b(?:direct\s+bilirubin|bilirubin\s+direct|conjugated\s+bilirubin)\b', n_clean):
        return "bilirubin_direct"
    if re.search(r'\b(?:indirect\s+bilirubin|bilirubin\s+indirect|unconjugated\s+bilirubin)\b', n_clean):
        return "bilirubin_indirect"
    if re.search(r'\b(?:total\s+bilirubin|bilirubin\s+total|bilirubin)\b', n_clean):
        return "bilirubin_total"

    # 18. Proteins
    if re.search(r'\b(?:a[\s/]*g\s+ratio|ag\s+ratio|albumin\s+globulin\s+ratio)\b', n_clean):
        return "ag_ratio"
    if re.search(r'\balbumin\b', n_clean):
        return "albumin"
    if re.search(r'\bglobulin\b', n_clean):
        return "globulin"
    if re.search(r'\b(?:total\s+protein|serum\s+protein)\b', n_clean):
        return "total_protein"

    # 19. Renal Function
    if re.search(r'\b(?:estimated\s+gfr|egfr|gfr)\b', n_clean):
        return "egfr"
    if re.search(r'\b(?:serum\s+creatinine|creatinine)\b', n_clean):
        return "creatinine"
    if re.search(r'\b(?:blood\s+urea\s+nitrogen|bun|urea\s+nitrogen)\b', n_clean):
        return "bun"
    if re.search(r'\b(?:blood\s+urea|urea)\b', n_clean):
        return "urea"
    if re.search(r'\b(?:serum\s+uric\s+acid|uric\s+acid|urate)\b', n_clean):
        return "uric_acid"

    # 20. Electrolytes & Minerals
    if re.search(r'\b(?:sodium|na\+?)\b', n_clean):
        return "sodium"
    if re.search(r'\b(?:potassium|k\+?)\b', n_clean):
        return "potassium"
    if re.search(r'\b(?:chloride|cl-?)\b', n_clean):
        return "chloride"
    if re.search(r'\b(?:calcium|ca\+?2?)\b', n_clean):
        return "calcium"
    if re.search(r'\b(?:magnesium|mg\+?2?)\b', n_clean):
        return "magnesium"
    if re.search(r'\b(?:phosphorus|phosphate)\b', n_clean):
        return "phosphorus"

    # 21. Iron & Vitamins
    if re.search(r'\b(?:total\s+iron\s+binding\s+capacity|tibc)\b', n_clean):
        return "tibc"
    if re.search(r'\b(?:transferrin\s+saturation|transferrin)\b', n_clean):
        return "transferrin_saturation"
    if re.search(r'\b(?:serum\s+iron|iron|fe)\b', n_clean):
        return "iron"
    if re.search(r'\b(?:serum\s+ferritin|ferritin)\b', n_clean):
        return "ferritin"
    if re.search(r'\b(?:25\s*-?\s*oh\s+vitamin\s+d|vitamin\s+d3?|vit\s+d3?|25\s*-?\s*hydroxy\s*vitamin\s+d|calcidiol|25\s*-?\s*oh\s*-?\s*d)\b', n_clean):
        return "vitamin_d"
    if re.search(r'\b(?:vitamin\s+b12|vit\s+b12|b12|cobalamin|cyanocobalamin)\b', n_clean):
        return "vitamin_b12"
    if re.search(r'\b(?:folate|folic\s+acid|vitamin\s+b9)\b', n_clean):
        return "folate"

    # 22. Differential WBC & Indices
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
    if re.search(r'\b(?:mean\s+platelet\s+volume|mpv)\b', n_clean):
        return "mpv"

    # 23. Cardiac, Coagulation & Enzymes
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

    # 23b. Thyroid Antibodies (MUST precede Triglycerides to avoid \btg\b false positives)
    if re.search(r'\b(?:anti[\s-]*tpo|thyroid\s+peroxidase|tpo\s+antibod(?:y|ies))\b', n_clean):
        return "anti_tpo"
    if re.search(r'\b(?:anti[\s-]*thyroglobulin|anti[\s-]*tg|thyroglobulin\s+antibod(?:y|ies)|atg)\b', n_clean):
        return "anti_tg"

    # 24. Lipids (LDL, HDL, Triglycerides, Total Cholesterol)
    if re.search(r'\b(?:ldl\s+cholesterol|ldl(?:\s*-\s*c)?)\b', n_clean):
        return "ldl"
    if re.search(r'\b(?:hdl\s+cholesterol|hdl(?:\s*-\s*c)?)\b', n_clean):
        return "hdl"
    if re.search(r'\b(?:triglycerides?|(?<!anti\s)(?<!anti-)tg)\b', n_clean):
        return "triglycerides"
    if re.search(r'\b(?:total\s+cholesterol|cholesterol\s+total|cholesterol)\b', n_clean):
        return "cholesterol"

    # Fallback normalization
    for prefix in ["serum ", "total ", "blood "]:
        if n_clean.startswith(prefix) and n_clean != "total cholesterol":
            n_clean = n_clean[len(prefix):].strip()

    return re.sub(r'\s+', '_', n_clean)


def convert_to_standard(
    value: Any,
    from_unit: str | None,
    to_unit: str | None,
    biomarker_key: str | None = "",
) -> float | None:
    """
    Converts a biomarker numeric value between standard clinical units.
    Supported conversions:
      - Glucose (fasting_glucose, glucose): mg/dL <-> mmol/L (factor 18.018)
      - Creatinine (creatinine): mg/dL <-> µmol/L (factor 88.4)
      - Cholesterol (cholesterol, ldl, hdl, vldl): mg/dL <-> mmol/L (factor 38.67)
      - Triglycerides (triglycerides): mg/dL <-> mmol/L (factor 88.57)
    Returns the converted float, or None if unsupported or invalid.
    """
    if value is None or from_unit is None or to_unit is None:
        return None
    val = _parse_first_float(str(value))
    if val is None:
        return None

    u_from = normalize_clinical_unit(from_unit).strip().lower().replace(" ", "")
    u_to = normalize_clinical_unit(to_unit).strip().lower().replace(" ", "")
    if not u_from or not u_to:
        return None
    if u_from == u_to:
        return val

    key = (biomarker_key or "").strip().lower()

    # 1. Glucose: mg/dL <-> mmol/L (18.018)
    if key in ("glucose", "fasting_glucose") or re.search(r'\b(?:glucose|fbs|fbg|blood_sugar)\b', key):
        if u_from == "mmol/l" and u_to == "mg/dl":
            return round(val * 18.018, 4)
        if u_from == "mg/dl" and u_to == "mmol/l":
            return round(val / 18.018, 4)

    # 2. Creatinine: mg/dL <-> µmol/L (88.4)
    if key == "creatinine" or re.search(r'\bcreatinine\b', key):
        if u_from == "mg/dl" and u_to in ("µmol/l", "umol/l", "μmol/l"):
            return round(val * 88.4, 4)
        if u_from in ("µmol/l", "umol/l", "μmol/l") and u_to == "mg/dl":
            return round(val / 88.4, 4)

    # 3. Cholesterol (Total, LDL, HDL): mg/dL <-> mmol/L (38.67)
    if key in ("cholesterol", "ldl", "hdl", "vldl") or re.search(r'\b(?:cholesterol|ldl|hdl|vldl)\b', key):
        if u_from == "mmol/l" and u_to == "mg/dl":
            return round(val * 38.67, 4)
        if u_from == "mg/dl" and u_to == "mmol/l":
            return round(val / 38.67, 4)

    # 4. Triglycerides: mg/dL <-> mmol/L (88.57)
    if key in ("triglycerides", "tg") or re.search(r'\b(?:triglycerides?|tg)\b', key):
        if u_from == "mmol/l" and u_to == "mg/dl":
            return round(val * 88.57, 4)
        if u_from == "mg/dl" and u_to == "mmol/l":
            return round(val / 88.57, 4)

    return None


# Backward-compatible alias
canonical_biomarker_name = canonical_biomarker_key


def _parse_first_float(s: Any) -> float | None:
    if s is None:
        return None
    text = str(s).strip()

    # Return None for ratio/titer or interval range strings
    if re.search(r'\b\d+\s*:\s*\d+\b', text):
        return None
    if re.search(r'-?\d+(?:\.\d+)?\s*(?:[-–—]|to)\s*-?\d+(?:\.\d+)?', text):
        return None

    # Strip comparator prefixes
    text = re.sub(r'^[<>≤≥=\s]+', '', text).strip()

    # Normalize thousands and decimal commas (handles 150,000, 2,38,000, 4,500.50, 3,9)
    if '.' in text and ',' in text:
        if text.rfind(',') < text.rfind('.'):
            text = text.replace(',', '')
        else:
            text = text.replace('.', '').replace(',', '.')
    elif text.count(',') > 1:
        text = text.replace(',', '')
    elif ',' in text:
        if re.search(r',\d{3}$', text):
            text = text.replace(',', '')
        elif re.search(r',\d{1,2}$', text):
            text = text.replace(',', '.')

    m = re.search(r'[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?', text)
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
    "creatinine",
    "urea",
    "bun",
    "alt",
    "ast",
    "alp",
    "bilirubin_total",
    "sodium",
    "potassium",
    "calcium",
    "fasting_glucose",
    "glucose_fasting",
    "glucose",
    "hba1c",
    "tsh",
}


def compute_biomarker_delta(
    current_val_str: str,
    prev_val_str: str,
    status: str = "Normal",
    unit: str = "",
    canonical_key: str = "",
    prev_unit: str = "",
) -> tuple[str | None, str | None, str | None]:
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

    if unit and prev_unit:
        u1 = normalize_clinical_unit(unit).strip().lower().replace(" ", "")
        u2 = normalize_clinical_unit(prev_unit).strip().lower().replace(" ", "")
        if u1 and u2 and u1 != u2:
            conv = convert_to_standard(p_val, prev_unit, unit, canonical_key)
            if conv is not None:
                p_val = conv
            else:
                return (None, None, None)

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


def is_sample_document(doc_or_val: Any) -> bool:
    """
    Returns True if the document, filename, or title represents a sample/demo report.
    Matches:
      - title or filename starting with / containing '[sample]' or 'sample report'
      - filename starting with 'sample_' or 'sample-' or containing 'sample_report' / 'sample.pdf'
      - title starting with 'sample report:' or '[sample]'
    """
    if doc_or_val is None:
        return False

    title = getattr(doc_or_val, "title", None)
    filename = getattr(doc_or_val, "filename", None)

    if isinstance(doc_or_val, dict):
        title = doc_or_val.get("title") or title
        filename = doc_or_val.get("filename") or filename

    candidates = []
    if isinstance(doc_or_val, str):
        candidates.append(doc_or_val)
    if title and isinstance(title, str):
        candidates.append(title)
    if filename and isinstance(filename, str):
        candidates.append(filename)

    for cand in candidates:
        low = cand.strip().lower()
        if (
            "[sample]" in low
            or low.startswith("sample report")
            or low.startswith("sample_report")
            or low.startswith("sample-report")
            or low.startswith("sample_")
            or low.startswith("sample-")
            or "sample_report.pdf" in low
            or "sample.pdf" in low
            or "(sample)" in low
            or "sample blood" in low
            or "sample test" in low
            or low == "sample"
        ):
            return True

    return False


