import uuid
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.db.database import AsyncSessionLocal
from app.db.models import User
from app.core.auth import create_access_token


@pytest.mark.asyncio
async def test_firebase_token_authenticates_and_provisions_new_user():
    random_id = uuid.uuid4().hex[:8]
    fb_email = f"firebase_user_{random_id}@gmail.com"
    mock_decoded_token = {
        "uid": f"firebase_uid_{random_id}",
        "email": fb_email,
        "name": "Jane Google",
    }

    mock_fb_auth = MagicMock()
    mock_fb_auth.verify_id_token.return_value = mock_decoded_token

    mock_fb_admin = MagicMock()
    mock_fb_admin._apps = [True]
    mock_fb_admin.auth = mock_fb_auth

    with patch.dict("sys.modules", {"firebase_admin": mock_fb_admin, "firebase_admin.auth": mock_fb_auth}):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = {"Authorization": "Bearer fake_firebase_token_xyz"}
            res = await ac.get("/users/me", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["email"] == fb_email
            assert data["full_name"] == "Jane Google"

    # Verify user now exists in the database
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).filter(User.email == fb_email))
        user = result.scalars().first()
        assert user is not None
        assert user.full_name == "Jane Google"
        assert user.phi_consent_granted is True


@pytest.mark.asyncio
async def test_firebase_token_existing_user():
    random_id = uuid.uuid4().hex[:8]
    fb_email = f"existing_fb_{random_id}@gmail.com"

    # Pre-create user in DB
    async with AsyncSessionLocal() as session:
        existing_user = User(
            email=fb_email,
            hashed_password="some_hashed_password",
            full_name="Existing Jane",
            phi_consent_granted=True,
        )
        session.add(existing_user)
        await session.commit()

    mock_decoded_token = {
        "uid": f"firebase_uid_{random_id}",
        "email": fb_email,
        "name": "Existing Jane",
    }

    mock_fb_auth = MagicMock()
    mock_fb_auth.verify_id_token.return_value = mock_decoded_token

    mock_fb_admin = MagicMock()
    mock_fb_admin._apps = [True]
    mock_fb_admin.auth = mock_fb_auth

    with patch.dict("sys.modules", {"firebase_admin": mock_fb_admin, "firebase_admin.auth": mock_fb_auth}):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = {"Authorization": "Bearer fake_firebase_token_xyz"}
            res = await ac.get("/users/me", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["email"] == fb_email
            assert data["full_name"] == "Existing Jane"


@pytest.mark.asyncio
async def test_fallback_to_local_jwt_when_firebase_token_fails():
    random_id = uuid.uuid4().hex[:8]
    jwt_email = f"local_jwt_{random_id}@test.com"

    async with AsyncSessionLocal() as session:
        user = User(
            email=jwt_email,
            hashed_password="hashed_pwd",
            full_name="Local User",
            phi_consent_granted=True,
        )
        session.add(user)
        await session.commit()

    local_token = create_access_token(data={"sub": jwt_email})

    mock_fb_auth = MagicMock()
    # Firebase verification fails because it's a local JWT
    mock_fb_auth.verify_id_token.side_effect = Exception("Invalid Firebase token")

    mock_fb_admin = MagicMock()
    mock_fb_admin._apps = [True]
    mock_fb_admin.auth = mock_fb_auth

    with patch.dict("sys.modules", {"firebase_admin": mock_fb_admin, "firebase_admin.auth": mock_fb_auth}):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = {"Authorization": f"Bearer {local_token}"}
            res = await ac.get("/users/me", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["email"] == jwt_email


@pytest.mark.asyncio
async def test_firebase_token_without_name_claim_provisions_user():
    random_id = uuid.uuid4().hex[:8]
    fb_email = f"email_password_user_{random_id}@example.com"
    # Typical email/password Firebase token: has email and uid, but NO name claim
    mock_decoded_token = {
        "uid": f"firebase_email_uid_{random_id}",
        "email": fb_email,
    }

    mock_fb_auth = MagicMock()
    mock_fb_auth.verify_id_token.return_value = mock_decoded_token

    mock_fb_admin = MagicMock()
    mock_fb_admin._apps = [True]
    mock_fb_admin.auth = mock_fb_auth

    with patch.dict("sys.modules", {"firebase_admin": mock_fb_admin, "firebase_admin.auth": mock_fb_auth}):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = {"Authorization": "Bearer fake_email_password_token"}
            res = await ac.get("/users/me", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["email"] == fb_email
            # Expected fallback to email prefix
            assert data["full_name"] == f"email_password_user_{random_id}"

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).filter(User.email == fb_email))
        user = result.scalars().first()
        assert user is not None
        assert user.full_name == f"email_password_user_{random_id}"
        assert user.phi_consent_granted is True
        assert len(user.hashed_password) > 0


@pytest.mark.asyncio
async def test_firebase_token_recovers_when_adc_credentials_fail():
    """Verify that when Firebase Admin throws 'cannot fetch credentials' / DefaultCredentialsError,
    the JWKS fallback successfully recovers and authenticates the user."""
    random_id = uuid.uuid4().hex[:8]
    fb_email = f"cred_recovery_{random_id}@example.com"
    
    # Create an RS256 token mimicking Firebase ID token
    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    project_id = "mediskye-backend"
    token = pyjwt.encode(
        {
            "iss": f"https://securetoken.google.com/{project_id}",
            "aud": project_id,
            "sub": f"uid_{random_id}",
            "email": fb_email,
            "name": "Recovery User",
        },
        private_pem,
        algorithm="RS256"
    )

    mock_fb_auth = MagicMock()
    mock_fb_auth.verify_id_token.side_effect = Exception("cannot fetch credentials from metadata server")

    mock_fb_admin = MagicMock()
    mock_fb_admin._apps = [True]
    mock_fb_admin.auth = mock_fb_auth

    with patch.dict("sys.modules", {"firebase_admin": mock_fb_admin, "firebase_admin.auth": mock_fb_auth}):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = {"Authorization": f"Bearer {token}"}
            res = await ac.get("/users/me", headers=headers)
            assert res.status_code == 200
            data = res.json()
            assert data["email"] == fb_email
            assert data["full_name"] == "Recovery User"


