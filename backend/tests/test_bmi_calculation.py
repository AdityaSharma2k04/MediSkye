import pytest
from app.core.clinical import compute_bmi_info
from app.rag.prompt_builder import (
    _format_patient_context,
    build_document_summary_prompt,
    generate_deterministic_fallback_summary,
)
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.dependent import DependentResponse, DependentUpdate, DependentCreate


def test_compute_bmi_info_edge_cases():
    assert compute_bmi_info(None, None) is None
    assert compute_bmi_info(175, None) is None
    assert compute_bmi_info(None, 70) is None
    assert compute_bmi_info(0, 70) is None
    assert compute_bmi_info(175, 0) is None
    assert compute_bmi_info(-175, 70) is None
    assert compute_bmi_info(175, -70) is None


def test_compute_bmi_info_categories():
    # Underweight: BMI < 18.5
    under = compute_bmi_info(180, 55)
    assert under is not None
    assert under["bmi"] == 17.0
    assert under["category"] == "Underweight"
    assert under["formatted"] == "17.0 kg/m² (Underweight)"

    # Normal weight: 18.5 <= BMI < 25.0
    normal = compute_bmi_info(178, 72)
    assert normal is not None
    assert normal["bmi"] == 22.7
    assert normal["category"] == "Normal weight"
    assert normal["formatted"] == "22.7 kg/m² (Normal weight)"

    # Overweight: 25.0 <= BMI < 30.0
    over = compute_bmi_info(174, 84)
    assert over is not None
    assert over["bmi"] == 27.7
    assert over["category"] == "Overweight"
    assert over["formatted"] == "27.7 kg/m² (Overweight)"

    # Obese: BMI >= 30.0
    obese = compute_bmi_info(170, 95)
    assert obese is not None
    assert obese["bmi"] == 32.9
    assert obese["category"] == "Obese"
    assert obese["formatted"] == "32.9 kg/m² (Obese)"


def test_format_patient_context_with_bmi():
    ctx = _format_patient_context(
        calculated_age=24,
        biological_sex="Male",
        pre_existing_conditions="None",
        current_medications="None",
        known_allergies="Pollen",
        height_cm=178.0,
        weight_kg=72.0,
        diet_type="vegetarian",
        activity_level="active",
        occupation="Software Engineer",
    )
    assert "Height: 178.0 cm" in ctx
    assert "Weight: 72.0 kg" in ctx
    assert "Calculated BMI: 22.7 kg/m² (Normal weight)" in ctx
    assert "Diet: vegetarian" in ctx
    assert "Activity level: active" in ctx


def test_build_document_summary_prompt_includes_patient_profile():
    profile = {
        "name": "Aditya Sharma",
        "calculated_age": 24,
        "biological_sex": "Male",
        "height_cm": 178.0,
        "weight_kg": 72.0,
        "bmi_info": compute_bmi_info(178.0, 72.0),
        "diet_type": "vegetarian",
        "pre_existing_conditions": "None",
        "current_medications": "None",
    }
    prompt = build_document_summary_prompt(
        "Hemoglobin: 14.5 g/dL",
        patient_profile=profile,
    )
    assert "<patient_profile>" in prompt
    assert "Aditya Sharma" in prompt
    assert "178.0 cm" in prompt
    assert "72.0 kg" in prompt
    assert "22.7 kg/m² (Normal weight)" in prompt
    assert "Patient Profile & BMI Snapshot" in prompt


def test_generate_deterministic_fallback_summary_includes_snapshot():
    profile = {
        "name": "Aditya Sharma",
        "calculated_age": 24,
        "biological_sex": "Male",
        "height_cm": 178.0,
        "weight_kg": 72.0,
        "bmi_info": compute_bmi_info(178.0, 72.0),
    }
    fallback = generate_deterministic_fallback_summary(
        "Glucose: 95 mg/dL",
        patient_profile=profile,
    )
    assert "**Patient Profile & BMI Snapshot:** Aditya Sharma" in fallback
    assert "178.0 cm" in fallback
    assert "72.0 kg" in fallback
    assert "22.7 kg/m² (Normal weight)" in fallback


def test_schema_weight_validation():
    # Valid update
    uu = UserUpdate(height_cm=175.0, weight_kg=70.0)
    assert uu.height_cm == 175.0
    assert uu.weight_kg == 70.0

    # Below min weight
    with pytest.raises(ValueError):
        UserUpdate(weight_kg=1.5)

    # Above max weight
    with pytest.raises(ValueError):
        UserUpdate(weight_kg=450.0)

    # Dependent create
    dep = DependentCreate(
        relationship="Brother",
        full_name="Aarav Verma",
        height_cm=180.0,
        weight_kg=78.0,
    )
    assert dep.height_cm == 180.0
    assert dep.weight_kg == 78.0
