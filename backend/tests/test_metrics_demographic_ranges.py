import pytest
from app.api.v1.endpoints.metrics import _resolve_status, _status_from_demographic_ranges

R1 = "Male: 13.8 - 17.2; Female: 12.1 - 15.1"
R2 = "M 13-17 / F 12-15"
R3 = "Adult Male 13.5–17.5 g/dL, Adult Female 12.0–16.0 g/dL"
R4 = "Men: 0.7-1.3 Women: 0.6-1.1"
R5 = "Adult: 4-10; Child: 5-13"


@pytest.mark.parametrize("value,rng,sex,expected", [
    ("14.5", R1, None, "Normal"),      # inside both strata
    ("12.5", R1, None, None),          # inside female only -> ambiguous
    ("12.5", R1, "female", "Normal"),
    ("12.5", R1, "male", "Low"),
    ("19", R1, None, "High"),
    ("11", R1, None, "Low"),
    ("11", R2, "female", "Low"),
    ("14", R2, "male", "Normal"),
    ("14", R3, None, "Normal"),
    ("1.2", R4, None, None),
    ("1.2", R4, "female", "High"),
    ("1.2", R4, "male", "Normal"),
    ("6", R5, None, None),              # age strata unresolved
    ("abc", R1, "male", None),
    ("14", "13.8 - 17.2", "male", None),  # single range is not this function's job
    ("14", R1, "other", "Normal"),
])
def test_status_from_demographic_ranges(value, rng, sex, expected):
    assert _status_from_demographic_ranges(value, rng, sex) == expected


@pytest.mark.parametrize("llm,value,rng,sex,expected", [
    ("Normal", "14.5", R1, None, "Normal"),
    ("Normal", "12.5", R1, None, "Unknown"),
    ("Normal", "12.5", R1, "female", "Normal"),
    ("Normal", "12.5", R1, "male", "Low"),
    ("", "12.5", R1, None, "Unknown"),
    ("High", "12.5", R1, None, "High"),
    ("high", "12.5", R1, None, "high"),
    ("Critical", "2", R1, None, "Critical"),
    ("Normal", "14", "13.8 - 17.2", None, "Normal"),
    ("Normal", "260", "< 200", None, "High"),
    ("", "190", "< 200", None, "Normal"),
    ("", "5", "", None, "Unknown"),
    ("Borderline", "5.8", "4.0-5.6", None, "Borderline"),
    ("Normal", "14", R2, None, "Normal"),
    ("Normal", "12.5", R2, None, "Unknown"),
])
def test_resolve_status(llm, value, rng, sex, expected):
    assert _resolve_status(llm, value, rng, sex) == expected
