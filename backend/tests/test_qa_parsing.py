import pytest
from app.rag.biomarkers import (
    parse_numeric_value,
    parse_reference_range,
    canonical_biomarker_key,
)
from app.services.clinical_units import (
    _parse_first_float,
    canonical_biomarker_key as cu_canonical_key,
)


def test_numeric_parsing_diverse_formats():
    # Thousands with decimals
    assert parse_numeric_value("4,500.50") == 4500.5
    assert _parse_first_float("4,500.50") == 4500.5

    # South Asian / Indian numbering (lakhs/crores)
    assert parse_numeric_value("2,38,000") == 238000.0
    assert _parse_first_float("2,38,000") == 238000.0
    assert parse_numeric_value("1,50,000.00") == 150000.0
    assert _parse_first_float("1,50,000.00") == 150000.0

    # Comparators
    assert parse_numeric_value("< 0.5") == 0.5
    assert _parse_first_float("< 0.5") == 0.5
    assert parse_numeric_value("> 60") == 60.0
    assert _parse_first_float("> 60") == 60.0
    assert parse_numeric_value(">= 90") == 90.0
    assert parse_numeric_value("<= 100") == 100.0

    # European decimal comma
    assert parse_numeric_value("3,9") == 3.9
    assert parse_numeric_value("12,50") == 12.50

    # Reference range with Indian thousands format
    rng = parse_reference_range("1,50,000 - 4,50,000")
    assert rng == {"type": "bounded", "low": 150000.0, "high": 450000.0}

    # Reference ranges with operators
    assert parse_reference_range("> 60") == {"type": "lower", "low": 60.0}
    assert parse_reference_range("Up to 35") == {"type": "upper", "high": 35.0}
    assert parse_reference_range("4.0 to 5.6") == {"type": "bounded", "low": 4.0, "high": 5.6}


def test_urinalysis_vs_serum_albumin():
    # Urine ACR maps to urine_acr
    assert canonical_biomarker_key("Urine Albumin to Creatinine Ratio") == "urine_acr"
    assert canonical_biomarker_key("uACR") == "urine_acr"
    assert cu_canonical_key("Urine Albumin to Creatinine Ratio") == "urine_acr"

    # Urine Albumin and Microalbumin MUST NOT match serum albumin
    assert canonical_biomarker_key("Urine Albumin") is None
    assert canonical_biomarker_key("Urine Microalbumin") is None
    assert cu_canonical_key("Urine Albumin") == ""
    assert cu_canonical_key("Urine Microalbumin") == ""

    # Serum albumin still maps to albumin
    assert canonical_biomarker_key("Serum Albumin") == "albumin"
    assert canonical_biomarker_key("Albumin") == "albumin"
    assert cu_canonical_key("Serum Albumin") == "albumin"


def test_explicit_overview_regex():
    import re
    pat = r"(?i)(?:^(?:now\s+)?(?:can\s+you\s+)?(?:give\s+me\s+)?(?:the\s+|a\s+)?(?:full|complete|entire)\s+(?:overview|breakdown|summary)(?:\s+of\s+(?:this|my|the)?\s*(?:report|results?|blood\s*work)?)?|\b(?:tell\s+me\s+about|explain|summarize|walk\s+me\s+through|give\s+me\s+(?:a|the)?\s*(?:full|complete|entire)?\s*(?:overview|breakdown|summary)\s*(?:of)?|(?:full|complete|entire)\s+(?:overview|breakdown|summary)\s*(?:of)?|overview\s+of)\s+(?:this|my|the|the\s+whole|the\s+entire)?\s*(?:report|lab\s+report|blood\s*work|results?))\b"

    positives = [
        "tell me about this report",
        "walk me through the whole report",
        "Now give me the full overview of this report",
        "full overview",
        "give me the full overview",
        "explain the entire report",
        "summarize my lab report",
        "can you give me a full overview of the report",
    ]
    for q in positives:
        assert re.search(pat, q.strip()) is not None, f"Expected match for: {q}"

    negatives = [
        "What is my HbA1c?",
        "what should I eat?",
        "what should I take care of?",
        "is this dangerous?",
        "tell me about my hemoglobin",
        "explain my creatinine",
        "how is my glucose?",
    ]
    for q in negatives:
        assert re.search(pat, q.strip()) is None, f"Expected NO match for: {q}"

