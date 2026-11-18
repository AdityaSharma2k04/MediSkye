import pytest
import urllib.parse
from app.rag.biomarkers import parse_numeric_value, _normalize_numeric_string, HIGH_ONLY_KEYS
from app.api.v1.endpoints.query import is_medication_change_query
from app.core.clinical import compute_bmi_info
from app.core.config import normalize_async_database_url
from app.core.auth import _single_flight, _INFLIGHT_RESOLUTIONS


def test_normalize_numeric_string_comma_decimals():
    # Leading zero with 3 decimals should parse as decimal
    assert _normalize_numeric_string("0,125") == "0.125"
    assert parse_numeric_value("0,125") == 0.125
    assert _normalize_numeric_string("0,800") == "0.800"
    assert parse_numeric_value("0,800") == 0.8
    # Standard thousands should still parse correctly
    assert _normalize_numeric_string("150,000") == "150000"
    assert parse_numeric_value("150,000") == 150000.0


def test_high_only_keys_includes_total_bilirubin():
    assert "total_bilirubin" in HIGH_ONLY_KEYS
    assert "bilirubin_total" in HIGH_ONLY_KEYS


def test_medication_change_regex_extended():
    assert is_medication_change_query("Should I take more metformin?") is True
    assert is_medication_change_query("Can I cut dose of atorvastatin?") is True
    assert is_medication_change_query("Is it okay to skip pill today?") is True
    assert is_medication_change_query("Took an extra dose of amlodipine") is True
    assert is_medication_change_query("Should I increase dose?") is True
    assert is_medication_change_query("Can I lower dose?") is True
    assert is_medication_change_query("What does high creatinine mean?") is False


def test_bmi_info_validation():
    assert compute_bmi_info(None, 70.0) is None
    assert compute_bmi_info(175.0, None) is None
    assert compute_bmi_info(0, 70.0) is None
    assert compute_bmi_info(-175.0, 70.0) is None
    assert compute_bmi_info(175.0, -70.0) is None
    assert compute_bmi_info(500.0, 70.0) is None  # Height > 300cm
    assert compute_bmi_info(175.0, 70.0)["category"] == "Normal weight"


def test_normalize_async_database_url_strips_statement_cache_size():
    raw_url = "postgresql+asyncpg://user:pass@ep-test.neon.tech/neondb?sslmode=require&statement_cache_size=0"
    normalized = normalize_async_database_url(raw_url)
    assert "statement_cache_size" not in normalized
    assert "ssl=require" in normalized


@pytest.mark.asyncio
async def test_single_flight_lock_release_on_error():
    test_key = "test_error_token_key"
    with pytest.raises(RuntimeError):
        async with _single_flight(test_key):
            raise RuntimeError("Boom inside flight")

    # Slot should be cleanly evicted after exception
    assert test_key not in _INFLIGHT_RESOLUTIONS
