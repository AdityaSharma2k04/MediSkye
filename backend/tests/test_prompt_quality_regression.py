from app.rag import prompt_builder as pb
from app.rag.biomarkers import (
    canonical_biomarker_key,
    build_extracted_biomarkers_and_hints,
    get_verified_absent_adjacent_tests,
)


def _rows(items):
    return [{"test": t, "value": v, "unit": u, "range": r, "status": s} for t, v, u, r, s in items]


MENON = _rows([
    ("Haemoglobin", "13.2", "g/dL", "13.0 - 17.0", "Normal"),
    ("Total Leucocyte Count (TLC)", "8.4", "10^3/µL", "4.0 - 11.0", "Normal"),
    ("Platelet Count", "238", "10^3/µL", "150 - 410", "Normal"),
    ("Fasting Plasma Glucose", "148", "mg/dL", "70 - 99", "High"),
    ("HbA1c (Glycated Haemoglobin)", "7.8", "%", "4.0 - 5.6", "High"),
    ("Creatinine, Serum", "1.8", "mg/dL", "0.70 - 1.30", "High"),
    ("eGFR (CKD-EPI 2021)", "38", "mL/min/1.73 m²", "> 60", "Low"),
    ("Blood Urea Nitrogen (BUN)", "34", "mg/dL", "7 - 20", "High"),
    ("Uric Acid", "7.9", "mg/dL", "3.5 - 7.2", "High"),
    ("Sodium", "139", "mmol/L", "135 - 145", "Normal"),
    ("Potassium", "5.3", "mmol/L", "3.5 - 5.1", "High"),
    ("Bilirubin, Total", "0.8", "mg/dL", "0.3 - 1.2", "Normal"),
    ("Aspartate Aminotransferase (AST/SGOT)", "62", "U/L", "0 - 40", "High"),
    ("Alanine Aminotransferase (ALT/SGPT)", "58", "U/L", "0 - 41", "High"),
    ("Alkaline Phosphatase (ALP)", "96", "U/L", "40 - 129", "Normal"),
    ("Gamma-Glutamyl Transferase (GGT)", "74", "U/L", "8 - 61", "High"),
    ("Total Cholesterol", "214", "mg/dL", "< 200", "High"),
    ("Triglycerides", "205", "mg/dL", "< 150", "High"),
    ("HDL Cholesterol", "41", "mg/dL", "> 40", "Normal"),
    ("LDL Cholesterol (Direct)", "138", "mg/dL", "< 100", "High"),
    ("Non-HDL Cholesterol", "173", "mg/dL", "< 130", "High"),
])

VERMA = _rows([
    ("TSH (Thyroid Stimulating Hormone)", "6.84", "µIU/mL", "0.40 - 4.20", "High"),
    ("Free T4 (FT4)", "0.82", "ng/dL", "0.93 - 1.70", "Low"),
    ("Free T3 (FT3)", "2.6", "pg/mL", "2.0 - 4.4", "Normal"),
    ("Anti-TPO Antibodies (Thyroid Peroxidase)", "212.4", "IU/mL", "< 34", "High"),
    ("Anti-Thyroglobulin Antibodies", "22.0", "IU/mL", "< 115", "Normal"),
    ("Vitamin D, 25-Hydroxy (Total)", "24.5", "ng/mL", "30 - 100", "Low"),
    ("Calcium, Total", "9.4", "mg/dL", "8.6 - 10.2", "Normal"),
    ("Total Cholesterol", "228", "mg/dL", "< 200", "High"),
    ("LDL Cholesterol (Direct)", "148", "mg/dL", "< 100", "High"),
    ("HDL Cholesterol", "52", "mg/dL", "> 50", "Normal"),
    ("Triglycerides", "118", "mg/dL", "< 150", "Normal"),
])


def _section(out, start, end):
    return out.split(start, 1)[1].split(end, 1)[0]


def test_british_spelling_is_recognised():
    assert canonical_biomarker_key("Haemoglobin") == "hemoglobin"
    assert canonical_biomarker_key("Hemoglobin") == "hemoglobin"
    assert canonical_biomarker_key("Haemoglobin A1c") == "hba1c"
    assert canonical_biomarker_key("HbA1c (Glycated Haemoglobin)") == "hba1c"


def test_acr_is_not_serum_creatinine():
    assert canonical_biomarker_key("Urine Albumin / Creatinine Ratio") == "urine_acr"
    assert canonical_biomarker_key("Creatinine, Serum") == "creatinine"
    assert canonical_biomarker_key("Serum Creatinine") == "creatinine"


def test_near_boundary_markers_are_listed():
    nb = _section(build_extracted_biomarkers_and_hints(MENON), "near_boundary_markers:", "followup_context:")
    assert "Haemoglobin" in nb and "HDL Cholesterol" in nb
    nb_v = _section(build_extracted_biomarkers_and_hints(VERMA), "near_boundary_markers:", "followup_context:")
    assert "HDL Cholesterol" in nb_v


def test_followup_hints_reach_the_block():
    follow = build_extracted_biomarkers_and_hints(MENON).split("followup_context:", 1)[1]
    assert "creatine kinase" in follow
    assert "ApoB" in follow


def test_acr_gets_no_serum_creatinine_hint():
    acr = _rows([("Urine Albumin / Creatinine Ratio", "48", "mg/g", "< 30", "High")])
    assert "Cystatin C" not in build_extracted_biomarkers_and_hints(acr)


def test_rbc_indices_absence_respects_british_spelling():
    names = ["Haemoglobin", "Total Leucocyte Count (TLC)", "Platelet Count",
             "Fasting Plasma Glucose", "Creatinine, Serum"]
    absent = get_verified_absent_adjacent_tests(names, "Haemoglobin 13.2 TLC 8.4 Platelet 238")
    assert any("Red blood cell indices" in line for line in absent)
    present = get_verified_absent_adjacent_tests(names, "Mean Corpuscular Haemoglobin Concentration 33")
    assert not any("Red blood cell indices" in line for line in present)


def test_prompt_wording_changes():
    r, s = pb.REPORT_WALKTHROUGH_RULES, pb.SHARED_CORE_RULES
    assert "single flagged value is common" not in r
    assert "fresh, one-sentence" not in r
    assert "Never call flagged results common, routine, or usual." in r
    assert "near_boundary_markers always gets its short interpretation" in r
    assert "this confirms" in s
    assert "lifestyle factors follow the lifestyle rule" in s


def test_build_prompt_still_assembles():
    system, user = pb.build_prompt("Explain my report", active_docs_metrics=MENON, raw_report_text="")
    assert "The Short Version" in system
    assert '<extracted_report_biomarkers count="21">' in user
    assert "[Flag: LOW-NORMAL" in user


def test_absent_test_rule_is_a_closed_list():
    r = pb.REPORT_WALKTHROUGH_RULES
    assert "These are the only bullets allowed here." in r
    assert "only items listed under verified_absent_adjacent_tests may be named as absent" in r
    assert "Do not name any other test as absent" not in r


def test_diagnosis_wording_rules_cover_variants():
    s = pb.SHARED_CORE_RULES
    assert "this confirms" in s
    assert "confirming" in s
    assert "point toward" in s


def test_heading_rules():
    r = pb.REPORT_WALKTHROUGH_RULES
    assert "own section titles" in r
    assert "plain text with no emoji" in r
    assert "Never use a single heading when there are more than six markers." in r


def test_next_steps_and_questions_do_not_presuppose_lifestyle():
    assert pb.REPORT_WALKTHROUGH_RULES.count("presuppose") >= 2
