import uuid
from types import SimpleNamespace
import pytest
from app.db.database import AsyncSessionLocal
from app.db.models import User, DependentProfile
from app.api.v1.endpoints.metrics import _resolve_status, _status_from_demographic_ranges, _load_patient_sex
from app.services.clinical_units import canonical_biomarker_key

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


@pytest.mark.asyncio
async def test_load_patient_sex_user_female_no_dependent():
    uid = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        session.add(User(id=uid, email=f"fem_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw", biological_sex="Female"))
        await session.commit()
        doc = SimpleNamespace(user_id=uid, dependent_id=None)
        assert await _load_patient_sex(session, doc) == "female"


@pytest.mark.asyncio
async def test_load_patient_sex_dependent_male_overrides_user():
    uid = uuid.uuid4()
    dep_id = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        session.add(User(id=uid, email=f"dep_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw", biological_sex="Female"))
        session.add(DependentProfile(id=dep_id, user_id=uid, relationship="child", full_name="Son", biological_sex="Male"))
        await session.commit()
        doc = SimpleNamespace(user_id=uid, dependent_id=dep_id)
        assert await _load_patient_sex(session, doc) == "male"


@pytest.mark.asyncio
async def test_load_patient_sex_user_prefer_not_to_say():
    uid = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        session.add(User(id=uid, email=f"pnts_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw", biological_sex="Prefer not to say"))
        await session.commit()
        doc = SimpleNamespace(user_id=uid, dependent_id=None)
        assert await _load_patient_sex(session, doc) is None


@pytest.mark.asyncio
async def test_load_patient_sex_user_none():
    uid = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        session.add(User(id=uid, email=f"none_{uuid.uuid4().hex[:8]}@test.com", hashed_password="pw", biological_sex=None))
        await session.commit()
        doc = SimpleNamespace(user_id=uid, dependent_id=None)
        assert await _load_patient_sex(session, doc) is None


def test_remediation_clinical_status_and_biomarkers():
    # EU decimal commas
    assert _resolve_status("Normal", "6,8", "3,9 - 5,6", None) == "High"

    # Comparator values
    assert _resolve_status("Normal", "> 200", "10 - 200", None) == "High"
    assert _resolve_status("Normal", "< 0.5", "< 1.0", None) == "Normal"

    # Trailing units in range
    assert _resolve_status("Normal", "18.5", "13.5 - 17.5 g/dL", None) == "High"

    # Qualitative serology
    assert _resolve_status("Normal", "Positive (1:160)", "Negative", None) == "High"

    # Canonical biomarker keys
    assert canonical_biomarker_key("Non-HDL Cholesterol") == "non_hdl"
    assert canonical_biomarker_key("MCHC") == "mchc"
    assert canonical_biomarker_key("Total Leucocyte Count (TLC)") == "wbc"



