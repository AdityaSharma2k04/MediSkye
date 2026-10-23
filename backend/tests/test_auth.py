import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_send_custom_verification_success():
    test_email = "patient@example.com"
    fake_link = "https://mediskye.firebaseapp.com/__/auth/action?mode=verifyEmail&apiKey=fakeApiKey"

    with patch("firebase_admin.auth.generate_email_verification_link", return_value=fake_link) as mock_gen_link, \
         patch("app.api.v1.endpoints.auth.send_email_via_gmail", new_callable=AsyncMock) as mock_send_email:

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/send-custom-verification",
                json={"email": test_email}
            )

        assert response.status_code == 200
        assert response.json() == {"message": "Verification email sent"}

        # Verify Firebase Admin SDK was called to generate the verification link
        mock_gen_link.assert_called_once_with(test_email)

        mock_send_email.assert_awaited_once()
        sent = mock_send_email.await_args.kwargs
        assert sent["to_email"] == test_email
        assert sent["subject"] == "Verify your email to start using MediSkye 🩺"
        assert fake_link in sent["html_body"]
        assert "Verify my email" in sent["html_body"]


@pytest.mark.asyncio
async def test_send_custom_verification_user_not_found():
    test_email = "nonexistent@example.com"

    with patch("firebase_admin.auth.generate_email_verification_link", side_effect=Exception("User not found")) as mock_gen_link, \
         patch("app.api.v1.endpoints.auth.send_email_via_gmail", new_callable=AsyncMock) as mock_send_email:

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/send-custom-verification",
                json={"email": test_email}
            )

        assert response.status_code == 400
        assert response.json()["detail"] == "Could not generate link. User may not exist."
        mock_gen_link.assert_called_once_with(test_email)
        mock_send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_custom_verification_invalid_email():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/auth/send-custom-verification",
            json={"email": "invalid-email-format"}
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_send_custom_verification_smtp_error():
    test_email = "patient@example.com"
    fake_link = "https://mediskye.firebaseapp.com/__/auth/action?mode=verifyEmail&apiKey=fakeApiKey"

    with patch("firebase_admin.auth.generate_email_verification_link", return_value=fake_link), \
         patch("app.api.v1.endpoints.auth.send_email_via_gmail", new_callable=AsyncMock, side_effect=OSError("SMTP unavailable")):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/send-custom-verification",
                json={"email": test_email}
            )

        assert response.status_code == 502
        assert response.json()["detail"] == "Email service is currently unavailable. Please try again later."


@pytest.mark.asyncio
async def test_send_custom_password_reset_success():
    test_email = "patient@example.com"
    fake_reset_link = "https://mediskye.firebaseapp.com/__/auth/action?mode=resetPassword&apiKey=fakeApiKey"

    with patch("firebase_admin.auth.generate_password_reset_link", return_value=fake_reset_link) as mock_gen_link, \
         patch("app.api.v1.endpoints.auth.send_email_via_gmail", new_callable=AsyncMock) as mock_send_email:

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/send-custom-password-reset",
                json={"email": test_email}
            )

        assert response.status_code == 200
        assert response.json() == {"message": "If an account exists with this email, a reset link has been sent."}

        mock_gen_link.assert_called_once_with(test_email)
        mock_send_email.assert_awaited_once()
        sent = mock_send_email.await_args.kwargs
        assert sent["to_email"] == test_email
        assert sent["subject"] == "Reset your MediSkye password 🔒"
        assert fake_reset_link in sent["html_body"]
        assert "Reset my password" in sent["html_body"]


@pytest.mark.asyncio
async def test_send_custom_password_reset_user_not_found_prevents_enumeration():
    test_email = "nonexistent@example.com"

    with patch("firebase_admin.auth.generate_password_reset_link", side_effect=Exception("User not found")) as mock_gen_link, \
         patch("app.api.v1.endpoints.auth.send_email_via_gmail", new_callable=AsyncMock) as mock_send_email:

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/send-custom-password-reset",
                json={"email": test_email}
            )

        # Must return 200 with generic message and never attempt email delivery
        assert response.status_code == 200
        assert response.json() == {"message": "If an account exists with this email, a reset link has been sent."}
        mock_gen_link.assert_called_once_with(test_email)
        mock_send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_custom_password_reset_smtp_error():
    test_email = "patient@example.com"
    fake_reset_link = "https://mediskye.firebaseapp.com/__/auth/action?mode=resetPassword&apiKey=fakeApiKey"

    with patch("firebase_admin.auth.generate_password_reset_link", return_value=fake_reset_link), \
         patch("app.api.v1.endpoints.auth.send_email_via_gmail", new_callable=AsyncMock, side_effect=OSError("SMTP unavailable")):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/send-custom-password-reset",
                json={"email": test_email}
            )

        assert response.status_code == 502
        assert response.json()["detail"] == "Email service is currently unavailable. Please try again later."


@pytest.mark.asyncio
async def test_send_custom_password_reset_invalid_email():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/auth/send-custom-password-reset",
            json={"email": "not-an-email"}
        )

    assert response.status_code == 422
