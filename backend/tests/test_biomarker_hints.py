import pytest
from typing import List, Dict, Any

from app.rag.biomarkers import (
    canonical_biomarker_key,
    parse_numeric_value,
    parse_reference_range,
    resolve_status,
    evaluate_near_boundary_flag,
    get_verified_absent_adjacent_tests,
    build_extracted_biomarkers_and_hints,
)

# 6.1 Synthetic 20-Analyte Fixture (Test Patient, TEST-0001)
SYNTHETIC_20_ANALYTE_FIXTURE: List[Dict[str, Any]] = [
    {"test": "Hemoglobin (Hb)", "value": "14.8", "unit": "g/dL", "range": "13.0 - 17.0", "status": "Normal"},
    {"test": "Red Blood Cell Count (RBC)", "value": "4.9", "unit": "10^6/uL", "range": "4.5 - 5.5", "status": "Normal"},
    {"test": "Total Leukocyte Count (WBC)", "value": "6800", "unit": "/uL", "range": "4000 - 11000", "status": "Normal"},
    {"test": "Platelet Count", "value": "220000", "unit": "/uL", "range": "150000 - 450000", "status": "Normal"},
    {"test": "Serum Ferritin", "value": "44.0", "unit": "ng/mL", "range": "30.0 - 400.0", "status": "Normal"},
    {"test": "Fasting Plasma Glucose", "value": "88", "unit": "mg/dL", "range": "70 - 99", "status": "Normal"},
    {"test": "Glycated Hemoglobin (HbA1c)", "value": "5.2", "unit": "%", "range": "4.0 - 5.6", "status": "Normal"},
    {"test": "Blood Urea Nitrogen (BUN)", "value": "14", "unit": "mg/dL", "range": "7 - 20", "status": "Normal"},
    {"test": "Serum Creatinine", "value": "1.19", "unit": "mg/dL", "range": "0.70 - 1.25", "status": "Normal"},
    {"test": "Estimated GFR (eGFR)", "value": "98", "unit": "mL/min/1.73m2", "range": ">= 90", "status": "Normal"},
    {"test": "Serum Uric Acid", "value": "5.2", "unit": "mg/dL", "range": "3.5 - 7.2", "status": "Normal"},
    {"test": "Alanine Aminotransferase (ALT / SGPT)", "value": "24", "unit": "U/L", "range": "10 - 40", "status": "Normal"},
    {"test": "Aspartate Aminotransferase (AST / SGOT)", "value": "22", "unit": "U/L", "range": "10 - 40", "status": "Normal"},
    {"test": "Total Cholesterol", "value": "165", "unit": "mg/dL", "range": "< 200", "status": "Normal"},
    {"test": "HDL Cholesterol", "value": "52", "unit": "mg/dL", "range": ">= 40", "status": "Normal"},
    {"test": "LDL Cholesterol (Calculated)", "value": "85", "unit": "mg/dL", "range": "< 100", "status": "Normal"},
    {"test": "Triglycerides", "value": "110", "unit": "mg/dL", "range": "< 150", "status": "Normal"},
    {"test": "Thyroid Stimulating Hormone (TSH)", "value": "2.1", "unit": "uIU/mL", "range": "0.4 - 4.5", "status": "Normal"},
    {"test": "Vitamin B12 (Cyanocobalamin)", "value": "246.0", "unit": "pg/mL", "range": "211.0 - 911.0", "status": "Normal"},
    {"test": "25-Hydroxy Vitamin D (Total)", "value": "36.3", "unit": "ng/mL", "range": "30.0 - 100.0", "status": "Normal"},
]

SYNTHETIC_REPORT_RAW_TEXT = """
PATIENT REPORT
Patient Name: Test Patient
Patient ID: TEST-0001
Specimen Collection Date: 2026-10-15

TEST RESULTS:
Hemoglobin (Hb): 14.8 g/dL (13.0 - 17.0)
Red Blood Cell Count (RBC): 4.9 10^6/uL (4.5 - 5.5)
Total Leukocyte Count (WBC): 6800 /uL (4000 - 11000)
Platelet Count: 220000 /uL (150000 - 450000)
Serum Ferritin: 44.0 ng/mL (30.0 - 400.0)
Fasting Plasma Glucose: 88 mg/dL (70 - 99)
Glycated Hemoglobin (HbA1c): 5.2 % (4.0 - 5.6)
Blood Urea Nitrogen (BUN): 14 mg/dL (7 - 20)
Serum Creatinine: 1.19 mg/dL (0.70 - 1.25)
Estimated GFR (eGFR): 98 mL/min/1.73m2 (>= 90)
Serum Uric Acid: 5.2 mg/dL (3.5 - 7.2)
Alanine Aminotransferase (ALT / SGPT): 24 U/L (10 - 40)
Aspartate Aminotransferase (AST / SGOT): 22 U/L (10 - 40)
Total Cholesterol: 165 mg/dL (< 200)
HDL Cholesterol: 52 mg/dL (>= 40)
LDL Cholesterol (Calculated): 85 mg/dL (< 100)
Triglycerides: 110 mg/dL (< 150)
Thyroid Stimulating Hormone (TSH): 2.1 uIU/mL (0.4 - 4.5)
Vitamin B12 (Cyanocobalamin): 246.0 pg/mL (211.0 - 911.0)
25-Hydroxy Vitamin D (Total): 36.3 ng/mL (30.0 - 100.0)
"""


def test_canonical_biomarker_keys_all_20():
    expected = {
        "Hemoglobin (Hb)": "hemoglobin",
        "Red Blood Cell Count (RBC)": "rbc",
        "Total Leukocyte Count (WBC)": "wbc",
        "Platelet Count": "platelets",
        "Serum Ferritin": "ferritin",
        "Fasting Plasma Glucose": "glucose",
        "Glycated Hemoglobin (HbA1c)": "hba1c",
        "Blood Urea Nitrogen (BUN)": "bun",
        "Serum Creatinine": "creatinine",
        "Estimated GFR (eGFR)": "egfr",
        "Serum Uric Acid": "uric_acid",
        "Alanine Aminotransferase (ALT / SGPT)": "alt",
        "Aspartate Aminotransferase (AST / SGOT)": "ast",
        "Total Cholesterol": "total_cholesterol",
        "HDL Cholesterol": "hdl",
        "LDL Cholesterol (Calculated)": "ldl",
        "Triglycerides": "triglycerides",
        "Thyroid Stimulating Hormone (TSH)": "tsh",
        "Vitamin B12 (Cyanocobalamin)": "vitamin_b12",
        "25-Hydroxy Vitamin D (Total)": "vitamin_d",
    }
    for name, expected_key in expected.items():
        assert canonical_biomarker_key(name) == expected_key, f"Failed on {name}"


def test_canonical_biomarker_key_precedence_and_unknown():
    assert canonical_biomarker_key("Glycated Hemoglobin (HbA1c)") == "hba1c"
    assert canonical_biomarker_key("HbA1c") == "hba1c"
    assert canonical_biomarker_key("Hemoglobin Electrophoresis") == "hb_electrophoresis"
    assert canonical_biomarker_key("Hb Electrophoresis") == "hb_electrophoresis"
    assert canonical_biomarker_key("Hemoglobin") == "hemoglobin"
    assert canonical_biomarker_key("Hb") == "hemoglobin"
    assert canonical_biomarker_key("Unknown Random Biomarker XYZ 123") is None


def test_parse_numeric_value_and_range_formats():
    # Value parsing
    assert parse_numeric_value("14.8") == 14.8
    assert parse_numeric_value("150,000") == 150000.0
    assert parse_numeric_value("3,9") == 3.9
    assert parse_numeric_value("< 0.5") == 0.5
    assert parse_numeric_value(">= 90") == 90.0
    assert parse_numeric_value("Negative") is None
    assert parse_numeric_value("Reactive") is None
    assert parse_numeric_value("Positive (1:160)") is None
    assert parse_numeric_value("1:160") is None
    assert parse_numeric_value("garbage") is None

    # Range parsing
    # Bounded
    r1 = parse_reference_range("4.0 - 5.6")
    assert r1 == {"type": "bounded", "low": 4.0, "high": 5.6}
    r2 = parse_reference_range("0.70 – 1.25")
    assert r2 == {"type": "bounded", "low": 0.70, "high": 1.25}
    r3 = parse_reference_range("4.0 to 5.6")
    assert r3 == {"type": "bounded", "low": 4.0, "high": 5.6}
    r4 = parse_reference_range("3,9 - 5,6")
    assert r4 == {"type": "bounded", "low": 3.9, "high": 5.6}
    r5 = parse_reference_range("150,000 - 450,000 /uL")
    assert r5 == {"type": "bounded", "low": 150000.0, "high": 450000.0}

    # Lower-bounded
    r6 = parse_reference_range(">= 90")
    assert r6 == {"type": "lower", "low": 90.0}
    r7 = parse_reference_range("≥ 40")
    assert r7 == {"type": "lower", "low": 40.0}
    r8 = parse_reference_range("> 60")
    assert r8 == {"type": "lower", "low": 60.0}

    # Upper-bounded
    r9 = parse_reference_range("< 200")
    assert r9 == {"type": "upper", "high": 200.0}
    r10 = parse_reference_range("<= 100")
    assert r10 == {"type": "upper", "high": 100.0}
    r11 = parse_reference_range("≤ 150")
    assert r11 == {"type": "upper", "high": 150.0}

    # Invalid / qualitative
    assert parse_reference_range("Negative") is None
    assert parse_reference_range("random text") is None


def test_resolve_status_policy_and_mismatches():
    # 1. Normalizes stored_status and keeps it
    assert resolve_status(value="14.8", interval="13.0 - 17.0", stored_status="normal") == "Normal"
    assert resolve_status(value="25.0", interval="13.0 - 17.0", stored_status="critical") == "Critical"

    # 2. Status mismatch detection: stored status is Normal but parsed value is High
    mismatches = []
    st = resolve_status(
        value="25.0",
        interval="13.0 - 17.0",
        stored_status="Normal",
        test_name="Hemoglobin",
        status_mismatches=mismatches,
    )
    assert st == "Normal"  # Policy keeps stored status!
    assert len(mismatches) == 1
    assert "Hemoglobin: stored status 'Normal' differs from parsed numeric status 'High'" in mismatches[0]

    # 3. Derive status when stored_status is missing
    assert resolve_status(value="14.8", interval="13.0 - 17.0", stored_status=None) == "Normal"
    assert resolve_status(value="10.0", interval="13.0 - 17.0", stored_status=None) == "Low"
    assert resolve_status(value="20.0", interval="13.0 - 17.0", stored_status=None) == "High"

    # 4. Unclassified when range or value fails to parse
    assert resolve_status(value="Negative", interval="Negative", stored_status=None) == "Unclassified"
    assert resolve_status(value="14.8", interval=None, stored_status=None) == "Unclassified"


def test_exact_four_near_boundary_markers_on_20_analyte_fixture():
    result_xml = build_extracted_biomarkers_and_hints(
        active_docs_metrics=SYNTHETIC_20_ANALYTE_FIXTURE,
        raw_report_text=SYNTHETIC_REPORT_RAW_TEXT,
    )

    assert 'count="20"' in result_xml
    assert "<analysis_hints>" in result_xml

    # Verify exactly 4 near-boundary flags:
    # 1. Serum Ferritin: LOW-NORMAL (4% of range)
    assert "Serum Ferritin: LOW-NORMAL (4% of range" in result_xml
    # 2. Vitamin B12 (Cyanocobalamin): LOW-NORMAL (5% of range)
    assert "Vitamin B12 (Cyanocobalamin): LOW-NORMAL (5% of range" in result_xml
    # 3. 25-Hydroxy Vitamin D (Total): LOW-NORMAL (9% of range)
    assert "25-Hydroxy Vitamin D (Total): LOW-NORMAL (9% of range" in result_xml
    # 4. Serum Creatinine: HIGH-NORMAL (89% of range)
    assert "Serum Creatinine: HIGH-NORMAL (89% of range" in result_xml

    # Verify no other markers are flagged near-boundary
    assert "Hemoglobin (Hb): LOW-NORMAL" not in result_xml
    assert "Red Blood Cell Count (RBC): LOW-NORMAL" not in result_xml
    assert "Fasting Plasma Glucose: HIGH-NORMAL" not in result_xml
    assert "Estimated GFR (eGFR): LOW-NORMAL" not in result_xml


def test_all_11_near_boundary_edge_cases():
    # 1. ALT 14 on 10 - 40: position 0.133, but ALT is high-only key -> NOT flagged
    flag1 = evaluate_near_boundary_flag("alt", "14", "10 - 40", "U/L", "Normal")
    assert flag1 is None

    # 2. glucose 74 on 70 - 100: position 0.133, high-only key -> NOT flagged
    flag2 = evaluate_near_boundary_flag("glucose", "74", "70 - 100", "mg/dL", "Normal")
    assert flag2 is None

    # 3. ferritin 85 on 30 - 400 ng/mL: position 0.1486 <= 0.15, but value 85 >= 50.0 cap -> NOT flagged
    flag3 = evaluate_near_boundary_flag("ferritin", "85", "30 - 400", "ng/mL", "Normal")
    assert flag3 is None

    # 4. ferritin 40 on 30 - 400 ng/mL: position 0.027 <= 0.15 AND value < 50.0 -> flagged LOW-NORMAL (3% or 4%)
    flag4 = evaluate_near_boundary_flag("ferritin", "40", "30 - 400", "ng/mL", "Normal")
    assert flag4 is not None
    assert flag4[0] == "LOW-NORMAL"

    # 5. total cholesterol 170 on < 200: 170/200 = 0.85 < 0.90 -> NOT flagged
    flag5 = evaluate_near_boundary_flag("total_cholesterol", "170", "< 200", "mg/dL", "Normal")
    assert flag5 is None

    # 6. total cholesterol 185 on < 200: 185/200 = 0.925 >= 0.90 -> flagged HIGH-NORMAL
    flag6 = evaluate_near_boundary_flag("total_cholesterol", "185", "< 200", "mg/dL", "Normal")
    assert flag6 is not None
    assert flag6[0] == "HIGH-NORMAL"

    # 7. LDL 92 on < 100: 92/100 = 0.92 >= 0.90 -> flagged HIGH-NORMAL
    flag7 = evaluate_near_boundary_flag("ldl", "92", "< 100", "mg/dL", "Normal")
    assert flag7 is not None
    assert flag7[0] == "HIGH-NORMAL"

    # 8. vitamin D 38 ng/mL on 30 - 100 ng/mL: position 0.114 <= 0.15 AND value < 40.0 -> flagged LOW-NORMAL
    flag8 = evaluate_near_boundary_flag("vitamin_d", "38", "30 - 100", "ng/mL", "Normal")
    assert flag8 is not None
    assert flag8[0] == "LOW-NORMAL"

    # 9. vitamin D 85 nmol/L on 75 - 250 nmol/L: non-ng/mL unit -> 10% band -> 10/175 = 0.057 <= 0.10 -> flagged LOW-NORMAL
    flag9 = evaluate_near_boundary_flag("vitamin_d", "85", "75 - 250", "nmol/L", "Normal")
    assert flag9 is not None
    assert flag9[0] == "LOW-NORMAL"

    # 10. vitamin D 120 nmol/L on 75 - 250 nmol/L: 45/175 = 0.257 > 0.10 -> NOT flagged
    flag10 = evaluate_near_boundary_flag("vitamin_d", "120", "75 - 250", "nmol/L", "Normal")
    assert flag10 is None

    # 11. B12 160 pmol/L on 148 - 738 pmol/L: non-pg/mL unit -> 10% band -> 12/590 = 0.020 <= 0.10 -> flagged LOW-NORMAL
    flag11 = evaluate_near_boundary_flag("vitamin_b12", "160", "148 - 738", "pmol/L", "Normal")
    assert flag11 is not None
    assert flag11[0] == "LOW-NORMAL"

    # Free T4 0.9 ng/dL on 0.8 - 1.8 ng/dL: position 0.10 <= 0.15 -> flagged LOW-NORMAL
    flag12 = evaluate_near_boundary_flag("free_t4", "0.9", "0.8 - 1.8", "ng/dL", "Normal")
    assert flag12 is not None
    assert flag12[0] == "LOW-NORMAL"

    # eGFR 99 on >= 90: 99 > 1.05 * 90 (94.5) -> NOT flagged
    flag13 = evaluate_near_boundary_flag("egfr", "99", ">= 90", "mL/min/1.73m2", "Normal")
    assert flag13 is None

    # eGFR 92 on >= 90: 90 <= 92 <= 94.5 -> flagged LOW-NORMAL
    flag14 = evaluate_near_boundary_flag("egfr", "92", ">= 90", "mL/min/1.73m2", "Normal")
    assert flag14 is not None
    assert flag14[0] == "LOW-NORMAL"


def test_verified_absent_adjacent_tests():
    names = ["Hemoglobin (Hb)", "Serum Ferritin", "Thyroid Stimulating Hormone (TSH)", "Serum Creatinine", "Fasting Plasma Glucose"]

    # 1. < 5 metrics -> returns empty (none)
    assert get_verified_absent_adjacent_tests(names[:4], "Some raw report text") == []

    # 2. Empty raw text -> returns empty (none)
    assert get_verified_absent_adjacent_tests(names, "") == []

    # 3. Non-empty text with none of the adjacent tests present -> returns all 3 candidate lines
    lines = get_verified_absent_adjacent_tests(names, "Routine blood screening with no other tests.")
    assert len(lines) == 3
    assert any("Iron panel (Serum Iron, TIBC, Transferrin Saturation)" in l for l in lines)
    assert any("Red blood cell indices (MCV, MCH, MCHC, RDW)" in l for l in lines)
    assert any("Thyroid hormones (Free T4, Free T3)" in l for l in lines)

    # 4. Synonym in raw text suppresses the candidate
    # Mentioning MCV in raw text suppresses RBC indices
    lines_suppressed = get_verified_absent_adjacent_tests(names, "Patient had MCV evaluated previously.")
    assert not any("Red blood cell indices" in l for l in lines_suppressed)
    assert any("Iron panel" in l for l in lines_suppressed)
    assert any("Thyroid hormones" in l for l in lines_suppressed)


def test_urinalysis_exclusions_and_ratio_precedence():
    from app.services.clinical_units import canonical_biomarker_key as cu_canonical_key

    # 1. Urine ACR precedes exclusions and creatinine
    assert canonical_biomarker_key("Urine Albumin to Creatinine Ratio") == "urine_acr"
    assert canonical_biomarker_key("uACR") == "urine_acr"
    assert cu_canonical_key("Urine Albumin to Creatinine Ratio") == "urine_acr"
    assert cu_canonical_key("uACR") == "urine_acr"

    # 2. Urinalysis dipstick & microscopy rows return None / ""
    urine_markers = [
        "Leucocyte Esterase", "Leukocyte Esterase", "Pus Cells", "Epithelial Cells",
        "Specific Gravity", "Urobilinogen", "Nitrites", "Ketones", "Urinary Casts",
        "Crystals", "Bacteria", "Yeast", "Mucus"
    ]
    for um in urine_markers:
        assert canonical_biomarker_key(um) is None, f"{um} did not return None in biomarkers.py"
        assert cu_canonical_key(um) == "", f"{um} did not return '' in clinical_units.py"

    # 3. Explicit ratios return specific ratio keys or None / "" for generic ratio
    assert canonical_biomarker_key("TC/HDL Ratio") == "tc_hdl_ratio"
    assert canonical_biomarker_key("LDL/HDL Ratio") == "ldl_hdl_ratio"
    assert canonical_biomarker_key("TG/HDL Ratio") == "tg_hdl_ratio"
    assert canonical_biomarker_key("BUN/Creatinine Ratio") == "bun_creatinine_ratio"
    assert canonical_biomarker_key("AST/ALT Ratio") == "ast_alt_ratio"
    assert canonical_biomarker_key("A/G Ratio") == "ag_ratio"
    assert canonical_biomarker_key("Random Ratio") is None

    assert cu_canonical_key("TC/HDL Ratio") == "tc_hdl_ratio"
    assert cu_canonical_key("LDL/HDL Ratio") == "ldl_hdl_ratio"
    assert cu_canonical_key("TG/HDL Ratio") == "tg_hdl_ratio"
    assert cu_canonical_key("BUN/Creatinine Ratio") == "bun_creatinine_ratio"
    assert cu_canonical_key("AST/ALT Ratio") == "ast_alt_ratio"
    assert cu_canonical_key("A/G Ratio") == "ag_ratio"
    assert cu_canonical_key("Random Ratio") == ""


def test_pipe_delimited_output_and_clean_followup_hints():
    # Build a multi-flag fixture
    fixture = [
        {"test": "Serum Creatinine", "value": "1.6", "unit": "mg/dL", "range": "0.7 - 1.2", "status": "High"},
        {"test": "Potassium", "value": "2.8", "unit": "mmol/L", "range": "3.5 - 5.1", "status": "Low"},
        {"test": "Total Leukocyte Count (WBC)", "value": "13500", "unit": "/uL", "range": "4000 - 11000", "status": "High"},
        {"test": "Urinary Sediment", "value": "Abnormal", "unit": "", "range": "Normal", "status": "Abnormal"},
    ]
    res = build_extracted_biomarkers_and_hints(fixture)

    # 1. Pipe-delimited raw test names without status suffixes
    assert "out_of_range_markers: Serum Creatinine | Potassium | Total Leukocyte Count (WBC) | Urinary Sediment" in res
    assert "high_markers: Serum Creatinine | Total Leukocyte Count (WBC)" in res
    assert "low_markers: Potassium" in res
    assert "other_flagged_markers: Urinary Sediment" in res

    # 2. Status breakdown includes other flagged count
    assert "out_of_range_count: 4 (High: 2; Low: 1; Other Flagged: 1)" in res

    # 3. Clean followup hints: zero lifestyle assumptions
    for forbidden in ["exercise", "meat intake", "sun exposure", "purine"]:
        assert forbidden not in res.lower()

    # Creatinine hint should NOT contain uACR / urine albumin-to-creatinine ratio
    creatinine_hint = [l for l in res.split("\n") if "Serum Creatinine" in l and "Cystatin C" in l]
    assert len(creatinine_hint) == 1
    assert "albumin-to-creatinine" not in creatinine_hint[0].lower()
    assert "uacr" not in creatinine_hint[0].lower()

