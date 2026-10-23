from unittest.mock import AsyncMock, patch

import pytest

from app.services.email_service import send_email_via_gmail


@pytest.mark.asyncio
async def test_send_email_via_gmail_uses_configured_smtp_and_message():
    with patch.dict(
        "os.environ",
        {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": "465",
            "SMTP_USER": "sender@example.com",
            "SMTP_PASSWORD": "app-password",
        },
    ), patch("app.services.email_service.aiosmtplib.send", new_callable=AsyncMock) as smtp_send:
        await send_email_via_gmail(
            "recipient@example.com",
            "Test subject",
            "<p>Hello</p>",
        )

    smtp_send.assert_awaited_once()
    message = smtp_send.await_args.args[0]
    assert message["From"] == "MediSkye <sender@example.com>"
    assert message["To"] == "recipient@example.com"
    assert message["Subject"] == "Test subject"
    assert "<p>Hello</p>" in message.as_string()
    assert smtp_send.await_args.kwargs == {
        "hostname": "smtp.example.com",
        "port": 465,
        "start_tls": True,
        "username": "sender@example.com",
        "password": "app-password",
    }


@pytest.mark.asyncio
async def test_send_email_via_gmail_requires_credentials():
    with patch.dict("os.environ", {}, clear=True), patch(
        "app.services.email_service.aiosmtplib.send", new_callable=AsyncMock
    ) as smtp_send:
        with pytest.raises(RuntimeError, match="SMTP credentials are not configured"):
            await send_email_via_gmail("recipient@example.com", "Subject", "<p>Body</p>")

    smtp_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_email_via_gmail_reraises_smtp_failure():
    with patch.dict(
        "os.environ",
        {"SMTP_USER": "sender@example.com", "SMTP_PASSWORD": "app-password"},
    ), patch(
        "app.services.email_service.aiosmtplib.send",
        new_callable=AsyncMock,
        side_effect=OSError("SMTP unavailable"),
    ):
        with pytest.raises(OSError, match="SMTP unavailable"):
            await send_email_via_gmail("recipient@example.com", "Subject", "<p>Body</p>")
