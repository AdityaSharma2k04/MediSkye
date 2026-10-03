import pytest
from app.rag.specialist_router import (
    format_specialist_copy,
    get_recommended_specialists,
)


def test_format_specialist_copy():
    recs = [
        {"title": "A cardiologist", "description": "for heart & cholesterol findings"},
        {"title": "An endocrinologist", "description": "for blood sugar & diabetes"},
        {"title": "A nephrologist", "description": "for kidney function"},
    ]
    copy = format_specialist_copy(recs)
    assert "Based on these findings, you may want to consult:" in copy
    assert "- A cardiologist (for heart & cholesterol findings)" in copy
    assert "- An endocrinologist (for blood sugar & diabetes)" in copy
    assert "- A nephrologist (for kidney function)" in copy
    assert "These are general recommendations, not referrals. Discuss with your primary care physician first." in copy


@pytest.mark.asyncio
async def test_get_recommended_specialists_maps_flags():
    # Given abnormal_flags = ["hba1c", "ldl"]
    flags = ["hba1c", "ldl"]
    results = await get_recommended_specialists(None, flags)
    
    # assert the router returns endocrinologist + cardiologist
    specialties = [r["specialty"] for r in results]
    assert "Endocrinology" in specialties
    assert "Cardiology" in specialties
    assert len(results) == 2


@pytest.mark.asyncio
async def test_get_recommended_specialists_empty_flags():
    # Given empty flags, assert empty list
    results = await get_recommended_specialists(None, [])
    assert results == []


@pytest.mark.asyncio
async def test_get_recommended_specialists_unknown_flags():
    # Given unknown flag, assert it's ignored (no crash)
    flags = ["unknown_crazy_flag"]
    results = await get_recommended_specialists(None, flags)
    assert results == []
