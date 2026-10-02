import pytest
from app.rag.specialist_router import (
    is_placeholder_specialist,
    get_category_recommendations_for_flags,
    format_specialist_copy,
    get_recommended_specialists,
)
from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.db.models import Specialist


def test_is_placeholder_specialist():
    assert is_placeholder_specialist("Dr. Sarah Chen", "sarah.chen@mediskye.org | 555-0101") is True
    assert is_placeholder_specialist("Dr. Marcus Johnson", "555-0102") is True
    assert is_placeholder_specialist("Dr. Real Specialist", "contact@hospital.org | 123-456-7890") is False


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


def test_get_category_recommendations_for_flags():
    flags = ["Cholesterol", "HbA1c", "Creatinine"]
    cats = get_category_recommendations_for_flags(flags)
    specialties = [c["specialty"] for c in cats]
    assert "Cardiology" in specialties
    assert "Endocrinology" in specialties
    assert "Nephrology" in specialties


@pytest.mark.asyncio
async def test_get_recommended_specialists_gates_contacts_by_default():
    async with AsyncSessionLocal() as session:
        # Insert a real specialist and a fake specialist
        fake_sp = Specialist(
            name="Dr. Sarah Chen",
            specialty="Cardiology",
            keywords=["Cholesterol", "Lipid"],
            contact_info="sarah.chen@mediskye.org | 555-0101",
        )
        real_sp = Specialist(
            name="Dr. Jane Doe",
            specialty="Cardiology",
            keywords=["Cholesterol"],
            contact_info="clinic@stjude.org | 212-555-9999", # Note: 555- pattern might match
        )
        real_sp.contact_info = "clinic@stjude.org | 212-700-1234"
        session.add(fake_sp)
        session.add(real_sp)
        await session.commit()

        # SHOW_SPECIALIST_CONTACTS is False by default
        assert settings.SHOW_SPECIALIST_CONTACTS is False
        results = await get_recommended_specialists(session, ["Cholesterol"])
        
        # Fake specialist must not be in results
        names = [r["name"] for r in results]
        assert "Dr. Sarah Chen" not in names
        for r in results:
            assert r["contact_info"] is None
            if r.get("id"):
                assert "555-0101" not in str(r)
                assert "@mediskye.org" not in str(r)
