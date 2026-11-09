"""E7: CORS must use an explicit allow-list, never the "*" wildcard.

`allow_credentials=True` combined with `allow_origins=["*"]` is both insecure
and non-compliant with the W3C CORS spec (browsers reject the wildcard when
credentials are included).
"""
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import Settings, settings


@pytest.mark.asyncio
async def test_allowed_origin_preflight_succeeds():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.options(
            "/users/me",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.status_code == 200, res.text
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert res.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_disallowed_origin_is_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.options(
            "/users/me",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # No allow-origin header is emitted for an unknown origin, and Starlette
        # short-circuits the preflight with 400.
        assert res.headers.get("access-control-allow-origin") is None
        assert res.status_code == 400


def test_cors_config_never_wildcards_with_credentials():
    assert isinstance(settings.ALLOWED_ORIGINS, list)
    assert settings.ALLOWED_ORIGINS, "ALLOWED_ORIGINS must not be empty"
    assert "*" not in settings.ALLOWED_ORIGINS


def test_allowed_origins_parses_comma_separated_env_string():
    s = Settings(
        FERNET_KEY="test-fernet-key",
        JWT_SECRET_KEY="test-jwt-secret-key-at-least-32-characters-long",
        ALLOWED_ORIGINS="http://a.example, http://b.example",
    )
    assert s.ALLOWED_ORIGINS == ["http://a.example", "http://b.example"]


def test_allowed_origins_parses_json_array_env_string():
    s = Settings(
        FERNET_KEY="test-fernet-key",
        JWT_SECRET_KEY="test-jwt-secret-key-at-least-32-characters-long",
        ALLOWED_ORIGINS='["http://a.example", "http://b.example"]',
    )
    assert s.ALLOWED_ORIGINS == ["http://a.example", "http://b.example"]


@pytest.mark.asyncio
async def test_mediskye_pages_dev_allowed_and_arbitrary_pages_dev_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Apex mediskye.pages.dev allowed
        res1 = await ac.options(
            "/users/me",
            headers={"Origin": "https://mediskye.pages.dev", "Access-Control-Request-Method": "GET"},
        )
        assert res1.status_code == 200
        assert res1.headers.get("access-control-allow-origin") == "https://mediskye.pages.dev"

        # Preview branch under mediskye.pages.dev allowed
        res2 = await ac.options(
            "/users/me",
            headers={"Origin": "https://feat-preview.mediskye.pages.dev", "Access-Control-Request-Method": "GET"},
        )
        assert res2.status_code == 200
        assert res2.headers.get("access-control-allow-origin") == "https://feat-preview.mediskye.pages.dev"

        # Arbitrary Cloudflare Pages site rejected
        res3 = await ac.options(
            "/users/me",
            headers={"Origin": "https://malicious-attacker.pages.dev", "Access-Control-Request-Method": "GET"},
        )
        assert res3.headers.get("access-control-allow-origin") is None
        assert res3.status_code == 400

