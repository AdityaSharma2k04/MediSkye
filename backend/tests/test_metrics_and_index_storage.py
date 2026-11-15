import pytest
from pathlib import Path
from app.rag.index_storage import _extract_index_folder_name, _resolve_local_index_dir
from app.rag.biomarkers import canonical_biomarker_key
from app.api.v1.endpoints.metrics import _resolve_status
from app.llm.gemini_client import mark_model_unavailable, is_model_unavailable, get_fallback_models
from app.core.config import settings


def test_extract_index_folder_name_cross_platform():
    # Windows absolute path with backslashes
    win_path = r"C:\Users\Lenovo\AppData\Local\Temp\mediskye_indexes\user_123_doc_456.index"
    assert _extract_index_folder_name(win_path) == "user_123_doc_456.index"

    # Windows relative or forward-slash path
    mixed_path = "C:/Users/Lenovo/AppData/Local/Temp/mediskye_indexes/user_123_doc_456.index"
    assert _extract_index_folder_name(mixed_path) == "user_123_doc_456.index"

    # Linux posix path
    linux_path = "/tmp/mediskye_indexes/user_123_doc_456.index"
    assert _extract_index_folder_name(linux_path) == "user_123_doc_456.index"

    # Bare folder name
    bare_path = "user_123_doc_456.index"
    assert _extract_index_folder_name(bare_path) == "user_123_doc_456.index"


def test_resolve_local_index_dir():
    folder_name = "user_abc_doc_xyz.index"
    resolved = _resolve_local_index_dir(folder_name)
    assert resolved == Path(settings.INDEX_STORAGE_DIR) / folder_name

    # Windows path resolved properly on any OS
    win_path = r"C:\Temp\user_abc_doc_xyz.index"
    resolved_win = _resolve_local_index_dir(win_path)
    assert resolved_win == Path(settings.INDEX_STORAGE_DIR) / folder_name


def test_canonical_biomarker_key_urinalysis():
    assert canonical_biomarker_key("Colour", allow_urinalysis=True) == "urine_color"
    assert canonical_biomarker_key("Appearance", allow_urinalysis=True) == "urine_appearance"
    assert canonical_biomarker_key("Specific Gravity", allow_urinalysis=True) == "urine_specific_gravity"
    assert canonical_biomarker_key("Reaction (pH)", allow_urinalysis=True) == "urine_ph"
    assert canonical_biomarker_key("pH", allow_urinalysis=True) == "urine_ph"
    assert canonical_biomarker_key("Ketones", allow_urinalysis=True) == "urine_ketones"
    assert canonical_biomarker_key("Urobilinogen", allow_urinalysis=True) == "urine_urobilinogen"
    assert canonical_biomarker_key("Nitrite", allow_urinalysis=True) == "urine_nitrite"
    assert canonical_biomarker_key("Leucocyte Esterase", allow_urinalysis=True) == "urine_leukocyte_esterase"
    assert canonical_biomarker_key("Pus Cells (WBC)", allow_urinalysis=True) == "urine_pus_cells"
    assert canonical_biomarker_key("Red Blood Cells (RBC)", allow_urinalysis=True) == "urine_rbc" or canonical_biomarker_key("Urine RBC", allow_urinalysis=True) == "urine_rbc"
    assert canonical_biomarker_key("Epithelial Cells", allow_urinalysis=True) == "urine_epithelial_cells"
    assert canonical_biomarker_key("Casts", allow_urinalysis=True) == "urine_casts"
    assert canonical_biomarker_key("Crystals", allow_urinalysis=True) == "urine_crystals"
    assert canonical_biomarker_key("Bacteria", allow_urinalysis=True) == "urine_bacteria"
    assert canonical_biomarker_key("Urine Albumin / Creatinine Ratio") == "urine_acr"
    assert canonical_biomarker_key("Microalbumin", allow_urinalysis=True) == "urine_microalbumin"
    assert canonical_biomarker_key("Creatinine (Urine)", allow_urinalysis=True) == "urine_creatinine"


def test_canonical_biomarker_key_fallback_slug():
    # Unknown test name returns None (classified as unrecognized biomarker)
    res = canonical_biomarker_key("Custom Novel Oncology Marker Alpha-1")
    assert res is None


def test_resolve_status_qualitative():
    # Normal qualitative matches
    assert _resolve_status("Normal", "Clear", "Clear", None) == "Normal"
    assert _resolve_status("Normal", "Pale Yellow", "Pale Yellow", None) == "Normal"
    assert _resolve_status("Normal", "Negative", "Negative", None) == "Normal"
    assert _resolve_status("Normal", "Nil", "Nil", None) == "Normal"

    # Abnormal qualitative matches
    assert _resolve_status("Abnormal", "Trace", "Negative", None) in ("High", "Abnormal")
    assert _resolve_status("Normal", "Trace", "Negative", None) == "High"
    assert _resolve_status("Abnormal", "Positive (+)", "Negative", None) in ("High", "Abnormal")
    assert _resolve_status("Abnormal", "Calcium oxalate, occasional", "Nil", None) in ("High", "Abnormal")


def test_model_fallback_chain_and_unavailable():
    dummy_model = "test-model-404"
    assert not is_model_unavailable(dummy_model)
    mark_model_unavailable(dummy_model)
    assert is_model_unavailable(dummy_model)

    chain = get_fallback_models()
    assert dummy_model not in chain
