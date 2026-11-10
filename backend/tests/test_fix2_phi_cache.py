import pytest
import uuid
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.auth import create_access_token, get_current_user, get_cached_user_dto
from app.db.models import User
from app.db.database import AsyncSessionLocal

# Test for Fix 2: Safe UserDTO PHI Minimization

@pytest.mark.asyncio
async def test_user_dto_strips_clinical_phi_and_query_preserves_context(setup_test_database):
    user_id = uuid.uuid4()
    email = f"phi_test_{uuid.uuid4().hex[:8]}@example.com"

    async with AsyncSessionLocal() as session:
        user = User(
            id=user_id,
            email=email,
            hashed_password="fake_hashed_password",
            full_name="Jane Doe",
            known_allergies="Penicillin",
            current_medications="Metformin 500mg",
            pre_existing_conditions="Type 2 Diabetes",
            blood_type="O+",
            occupation="Engineer",
            phi_consent_granted=True,
            memory_consent_granted=True,
        )
        session.add(user)
        await session.commit()

    token = create_access_token(data={"sub": email, "jti": str(uuid.uuid4())})

    # Warm _TOKEN_CACHE via get_current_user
    async with AsyncSessionLocal() as session:
        cached_user = await get_current_user(token=token, db=session)
        assert cached_user.id == user_id

    # 1. Assert the cached UserDTO in _TOKEN_CACHE holds None for clinical PHI fields
    cached_dto = get_cached_user_dto(token)
    assert cached_dto is not None
    assert cached_dto.known_allergies is None, f"Expected None in cache, got {cached_dto.known_allergies}"
    assert cached_dto.current_medications is None, f"Expected None in cache, got {cached_dto.current_medications}"
    assert cached_dto.pre_existing_conditions is None
    assert cached_dto.blood_type is None
    assert cached_dto.occupation is None

    # 2. Call POST /query and assert "Penicillin" and "Metformin 500mg" STILL appear in the context sent to LLM
    chunk = MagicMock()
    chunk.text = "Consultation response"
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.return_value = [chunk]
    intent_resp = MagicMock()
    intent_resp.text = "GENERAL_HEALTH"
    mock_client.models.generate_content.return_value = intent_resp

    with patch("app.llm.gemini_client.get_genai_client", return_value=mock_client), \
         patch("app.api.v1.endpoints.query.get_genai_client", return_value=mock_client):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/query",
                json={"query": "What should I take for a headache?", "patient_id": "self"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200

    assert mock_client.models.generate_content_stream.called
    call_kwargs = mock_client.models.generate_content_stream.call_args.kwargs
    contents = str(call_kwargs.get("contents", ""))
    assert "Penicillin" in contents, f"Expected 'Penicillin' in LLM prompt: {contents}"
    assert "Metformin 500mg" in contents, f"Expected 'Metformin 500mg' in LLM prompt: {contents}"
