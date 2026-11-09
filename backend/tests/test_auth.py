import pytest
from firebase_admin.auth import UserNotFoundError
from unittest.mock import ANY, AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from app.api.v1.endpoints.auth import _build_mediskye_email_html
from app.core.config import settings
from app.main import app


@pytest.mark.asyncio
async def test_send_custom_verification_success():
    test_email = "patient@example.com"
    fake_link = "https://mediskye.firebaseapp.com/__/auth/action?mode=verifyEmail&apiKey=fakeApiKey&oobCode=verify-code"
    custom_link = "https://mediskye.pages.dev/auth/action?mode=verifyEmail&oobCode=verify-code"

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
        mock_gen_link.assert_called_once_with(test_email, action_code_settings=ANY)
        settings = mock_gen_link.call_args.kwargs["action_code_settings"]
        assert settings.url == "https://mediskye.pages.dev/auth/action"
        assert settings.handle_code_in_app is True

        mock_send_email.assert_awaited_once()
        sent = mock_send_email.await_args.kwargs
        assert sent["to_email"] == test_email
        assert sent["subject"] == "Verify your email address — MediSkye"
        assert custom_link.replace("&", "&amp;") in sent["html_body"]
        assert "Verify Email Address" in sent["html_body"]
        assert "Account: <strong" in sent["html_body"]
        assert test_email in sent["html_body"]
        assert "word-break: break-all" in sent["html_body"]
        assert "60 minutes" in sent["html_body"]


@pytest.mark.asyncio
async def test_send_custom_verification_user_not_found():
    test_email = "nonexistent@example.com"

    with patch("firebase_admin.auth.generate_email_verification_link", side_effect=UserNotFoundError("User not found")) as mock_gen_link, \
         patch("app.api.v1.endpoints.auth.send_email_via_gmail", new_callable=AsyncMock) as mock_send_email:

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/send-custom-verification",
                json={"email": test_email}
            )

        assert response.status_code == 200
        assert response.json() == {"message": "Verification email sent"}
        mock_gen_link.assert_called_once_with(test_email, action_code_settings=ANY)
        mock_send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_custom_verification_generation_error_is_internal_server_error():
    test_email = "patient@example.com"

    with patch(
        "firebase_admin.auth.generate_email_verification_link",
        side_effect=OSError("Firebase unavailable"),
    ) as mock_gen_link, patch(
        "app.api.v1.endpoints.auth.send_email_via_gmail",
        new_callable=AsyncMock,
    ) as mock_send_email:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/send-custom-verification",
                json={"email": test_email},
            )

    assert response.status_code == 500
    assert response.json()["detail"] == "An internal error occurred."
    mock_gen_link.assert_called_once_with(test_email, action_code_settings=ANY)
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
    fake_link = "https://mediskye.firebaseapp.com/__/auth/action?mode=verifyEmail&apiKey=fakeApiKey&oobCode=verify-code"

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
    fake_reset_link = "https://mediskye.firebaseapp.com/__/auth/action?mode=resetPassword&apiKey=fakeApiKey&oobCode=reset-code"
    custom_link = "https://mediskye.pages.dev/auth/action?mode=resetPassword&oobCode=reset-code"

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

        mock_gen_link.assert_called_once_with(test_email, action_code_settings=ANY)
        settings = mock_gen_link.call_args.kwargs["action_code_settings"]
        assert settings.url == "https://mediskye.pages.dev/auth/action"
        assert settings.handle_code_in_app is True
        mock_send_email.assert_awaited_once()
        sent = mock_send_email.await_args.kwargs
        assert sent["to_email"] == test_email
        assert sent["subject"] == "Reset your password — MediSkye"
        assert custom_link.replace("&", "&amp;") in sent["html_body"]
        assert "Reset Password" in sent["html_body"]
        assert "Account: <strong" in sent["html_body"]
        assert test_email in sent["html_body"]
        assert "word-break: break-all" in sent["html_body"]
        assert "60 minutes" in sent["html_body"]


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
        mock_gen_link.assert_called_once_with(test_email, action_code_settings=ANY)
        mock_send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_custom_password_reset_smtp_error():
    test_email = "patient@example.com"
    fake_reset_link = "https://mediskye.firebaseapp.com/__/auth/action?mode=resetPassword&apiKey=fakeApiKey&oobCode=reset-code"

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


def test_mediskye_email_html_escapes_dynamic_content():
    email_html = _build_mediskye_email_html(
        preheader="<preheader>",
        badge_label="<badge>",
        heading="<heading>",
        intro_text="<intro>",
        recipient_email='" onmouseover="alert(1)',
        cta_label="<button>",
        action_url='https://mediskye.pages.dev/auth/action?code="unsafe"&next=<script>',
        security_note="<security>",
    )

    assert "&lt;preheader&gt;" in email_html
    assert "&lt;badge&gt;" in email_html
    assert "&lt;heading&gt;" in email_html
    assert "&lt;intro&gt;" in email_html
    assert "&quot; onmouseover=&quot;alert(1)" in email_html
    assert "&lt;button&gt;" in email_html
    assert 'href="https://mediskye.pages.dev/auth/action?code=&quot;unsafe&quot;&amp;next=&lt;script&gt;"' in email_html
    assert "&lt;security&gt;" in email_html


@pytest.mark.asyncio
async def test_send_custom_verification_background_tasks_dispatch():
    test_email = "async_patient@example.com"
    fake_link = "https://mediskye.firebaseapp.com/__/auth/action?mode=verifyEmail&apiKey=fakeApiKey&oobCode=verify-code"

    with patch("firebase_admin.auth.generate_email_verification_link", return_value=fake_link), \
         patch("app.api.v1.endpoints.auth.send_email_via_gmail", new_callable=AsyncMock) as mock_send_email:

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/send-custom-verification",
                json={"email": test_email},
                headers={"X-Sync-Email-Test": "0"},
            )

        assert response.status_code == 200
        assert response.json()["message"] == "Verification email sent"
        # Background tasks executed by Starlette ASGI transport after response
        mock_send_email.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_email_test_header_ignored_in_production():
    test_email = "prod_patient@example.com"
    fake_link = "https://mediskye.firebaseapp.com/__/auth/action?mode=verifyEmail&apiKey=fakeApiKey&oobCode=verify-code"

    with patch.object(settings, "ENV", "production"), \
         patch("firebase_admin.auth.generate_email_verification_link", return_value=fake_link), \
         patch("app.api.v1.endpoints.auth.send_email_via_gmail", new_callable=AsyncMock) as mock_send_email:

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/auth/send-custom-verification",
                json={"email": test_email},
                headers={"X-Sync-Email-Test": "1"},  # Should be ignored in production
            )

        assert response.status_code == 200
        assert response.json()["message"] == "Verification email sent"
        # In production, was added to BackgroundTasks, which AsyncClient completes on exit
        mock_send_email.assert_awaited_once()

