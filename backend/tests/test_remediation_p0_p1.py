import pytest
from app.services.clinical_units import (
    _parse_first_float,
    normalize_clinical_unit,
    canonical_biomarker_key,
    ALLOWED_DELTA_DROP_KEYS,
)
from app.api.v1.endpoints.metrics import _status_from_range, _resolve_status
from app.db.encryption import EncryptedString


def test_parse_first_float_eu_commas_and_thousands():
    assert _parse_first_float("6,8") == 6.8
    assert _parse_first_float("1,25") == 1.25
    assert _parse_first_float("11,200") == 11200.0
    assert _parse_first_float("250,000") == 250000.0
    assert _parse_first_float("1,000,000") == 1000000.0
    assert _parse_first_float("14.5") == 14.5
    assert _parse_first_float("< 0.5") == 0.5
    assert _parse_first_float(None) is None


def test_normalize_clinical_unit_indian_lab_units():
    assert normalize_clinical_unit("gm/dl") == "g/dL"
    assert normalize_clinical_unit("gm%") == "g/dL"
    assert normalize_clinical_unit("g/dl") == "g/dL"
    assert normalize_clinical_unit("mg/dl") == "mg/dL"
    assert normalize_clinical_unit("mill/cumm") == "10⁶/µL"
    assert normalize_clinical_unit("million/cumm") == "10⁶/µL"
    assert normalize_clinical_unit("thou/cumm") == "10³/µL"
    assert normalize_clinical_unit("thousand/cumm") == "10³/µL"


def test_status_from_range_comparators_and_trailing_units():
    # Comparator against upper range
    assert _status_from_range("< 0.5", "< 1.0") == "Normal"
    assert _status_from_range("<= 0.02", "< 1.0") == "Normal"
    assert _status_from_range("> 200", "< 100") == "High"
    assert _status_from_range(">= 100", "< 50") == "High"

    # Comparator against between range
    assert _status_from_range("< 0.02", "0.05 - 0.20") == "Low"
    assert _status_from_range("> 1.5", "0.2 - 1.0") == "High"

    # Trailing unit text on ranges
    assert _status_from_range("14.5", "13.5 - 17.5 g/dL") == "Normal"
    assert _status_from_range("18.0", "13.5 - 17.5 g/dL") == "High"
    assert _status_from_range("12.0", "13.5 - 17.5 g/dL") == "Low"
    assert _status_from_range("150", "< 200 mg/dL") == "Normal"
    assert _status_from_range("250", "< 200 mg/dL") == "High"

    # European decimal comma in range
    assert _status_from_range("6.8", "5,5 - 8,0") == "Normal"
    assert _status_from_range("4.2", "5,5 - 8,0") == "Low"
    assert _status_from_range("9.1", "5,5 - 8,0") == "High"


def test_resolve_status_qualitative_serology():
    # Positive / Reactive against Negative reference
    assert _resolve_status("", "Reactive", "Non-Reactive", None) == "High"
    assert _resolve_status("", "Positive", "Negative", None) == "High"
    assert _resolve_status("", "Detected", "Negative", None) == "High"
    assert _resolve_status("", "+2", "Negative", None) == "High"

    # Normal overriding LLM "Normal" on Reactive
    assert _resolve_status("Normal", "Reactive", "Non-Reactive", None) == "High"

    # Preserves Critical/Abnormal
    assert _resolve_status("Critical", "Reactive", "Non-Reactive", None) == "Critical"

    # Non-Reactive / Negative -> Normal
    assert _resolve_status("", "Non-Reactive", "Non-Reactive", None) == "Normal"
    assert _resolve_status("", "Negative", "Negative", None) == "Normal"
    assert _resolve_status("", "Absent", "Negative", None) == "Normal"


def test_canonical_biomarker_key_no_collisions():
    # Non-HDL and VLDL must NOT collide with HDL or Cholesterol
    assert canonical_biomarker_key("Non-HDL Cholesterol") == "non_hdl"
    assert canonical_biomarker_key("Non-HDL") == "non_hdl"
    assert canonical_biomarker_key("VLDL Cholesterol") == "vldl"
    assert canonical_biomarker_key("VLDL") == "vldl"
    assert canonical_biomarker_key("HDL Cholesterol") == "hdl"
    assert canonical_biomarker_key("Total Cholesterol") == "cholesterol"

    # MCHC, MCH, MCV must NOT collide with Hemoglobin
    assert canonical_biomarker_key("MCHC") == "mchc"
    assert canonical_biomarker_key("MCH") == "mch"
    assert canonical_biomarker_key("MCV") == "mcv"
    assert canonical_biomarker_key("Hemoglobin") == "hemoglobin"

    # Indian and international lab aliases
    assert canonical_biomarker_key("Total Leucocyte Count (TLC)") == "wbc"
    assert canonical_biomarker_key("TLC") == "wbc"
    assert canonical_biomarker_key("PCV") == "hematocrit"
    assert canonical_biomarker_key("Packed Cell Volume") == "hematocrit"
    assert canonical_biomarker_key("ESR") == "esr"
    assert canonical_biomarker_key("CRP") == "crp"
    assert canonical_biomarker_key("High Sensitivity CRP") == "crp"
    assert canonical_biomarker_key("TSH") == "tsh"
    assert canonical_biomarker_key("Free T3") == "free_t3"
    assert canonical_biomarker_key("Free T4") == "free_t4"
    assert canonical_biomarker_key("Total T3") == "t3"
    assert canonical_biomarker_key("Total T4") == "t4"
    assert canonical_biomarker_key("Alkaline Phosphatase (ALP)") == "alp"
    assert canonical_biomarker_key("Gamma GT (GGT)") == "ggt"
    assert canonical_biomarker_key("Bilirubin Direct") == "bilirubin_direct"
    assert canonical_biomarker_key("Bilirubin Indirect") == "bilirubin_indirect"
    assert canonical_biomarker_key("Total Bilirubin") == "bilirubin_total"
    assert canonical_biomarker_key("Albumin") == "albumin"
    assert canonical_biomarker_key("Globulin") == "globulin"
    assert canonical_biomarker_key("Total Protein") == "total_protein"
    assert canonical_biomarker_key("A/G Ratio") == "ag_ratio"
    assert canonical_biomarker_key("Serum Sodium") == "sodium"
    assert canonical_biomarker_key("Serum Potassium") == "potassium"
    assert canonical_biomarker_key("Chloride") == "chloride"
    assert canonical_biomarker_key("Calcium") == "calcium"
    assert canonical_biomarker_key("Magnesium") == "magnesium"
    assert canonical_biomarker_key("Phosphorus") == "phosphorus"
    assert canonical_biomarker_key("Serum Iron") == "iron"
    assert canonical_biomarker_key("TIBC") == "tibc"
    assert canonical_biomarker_key("Transferrin Saturation") == "transferrin_saturation"
    assert canonical_biomarker_key("Folate") == "folate"
    assert canonical_biomarker_key("Neutrophils") == "neutrophils"
    assert canonical_biomarker_key("Lymphocytes") == "lymphocytes"
    assert canonical_biomarker_key("Monocytes") == "monocytes"
    assert canonical_biomarker_key("Eosinophils") == "eosinophils"
    assert canonical_biomarker_key("Basophils") == "basophils"
    assert canonical_biomarker_key("RDW") == "rdw"
    assert canonical_biomarker_key("Mean Platelet Volume (MPV)") == "mpv"
    assert canonical_biomarker_key("PSA") == "psa"
    assert canonical_biomarker_key("Troponin I") == "troponin"
    assert canonical_biomarker_key("BNP") == "bnp"
    assert canonical_biomarker_key("PT/INR") == "inr"
    assert canonical_biomarker_key("APTT") == "aptt"
    assert canonical_biomarker_key("LDH") == "ldh"
    assert canonical_biomarker_key("Amylase") == "amylase"
    assert canonical_biomarker_key("Lipase") == "lipase"
    assert canonical_biomarker_key("CPK") == "ck"


def test_allowed_delta_drop_keys_expanded():
    expected_analytes = {
        "hemoglobin", "ferritin", "vitamin_b12", "vitamin_d",
        "platelets", "rbc", "wbc", "egfr", "creatinine",
        "urea", "bun", "alt", "ast", "alp", "bilirubin_total",
        "sodium", "potassium", "calcium", "fasting_glucose", "hba1c", "tsh"
    }
    for analyte in expected_analytes:
        assert analyte in ALLOWED_DELTA_DROP_KEYS, f"{analyte} missing from ALLOWED_DELTA_DROP_KEYS"


def test_encrypted_string_corrupt_token_returns_none():
    enc = EncryptedString()
    # Corrupt Fernet token prefix
    corrupt_token = "gAAAAABm_fake_corrupt_fernet_token_that_cannot_decrypt"
    result = enc.process_result_value(corrupt_token, None)
    assert result is None, f"Expected None for corrupt token, got: {result}"

    # Plaintext legacy value (doesn't start with gAAAA) returns as-is
    plain_result = enc.process_result_value("legacy_plaintext_value", None)
    assert plain_result == "legacy_plaintext_value"

