import pytest
from pydantic import ValidationError
from app.schemas.user import UserCreate


def test_password_validation_boundary_conditions():
    valid_email = "testuser@example.com"

    # 1. 100-character password -> raises ValidationError
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(
            email=valid_email,
            password="A" * 100,
            phi_consent_granted=True,
        )
    assert "password" in str(exc_info.value)

    # 2. 8-character password -> passes (minimum valid length)
    user_8 = UserCreate(
        email=valid_email,
        password="A" * 8,
        phi_consent_granted=True,
    )
    assert len(user_8.password) == 8

    # 3. 72-character password -> passes (maximum valid length for bcrypt)
    user_72 = UserCreate(
        email=valid_email,
        password="A" * 72,
        phi_consent_granted=True,
    )
    assert len(user_72.password) == 72

    # 4. 73-character password -> raises ValidationError (exceeds 72 bytes)
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(
            email=valid_email,
            password="A" * 73,
            phi_consent_granted=True,
        )
    assert "password" in str(exc_info.value)

    # 5. 7-character password -> raises ValidationError (under 8 chars)
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(
            email=valid_email,
            password="A" * 7,
            phi_consent_granted=True,
        )
    assert "password" in str(exc_info.value)
