import pytest
from pydantic import ValidationError
from cryptography.fernet import Fernet
from fastapi import FastAPI
from app.core.config import Settings
from app.main import lifespan


def test_settings_fails_when_fernet_key_unset(monkeypatch):
    monkeypatch.delenv("FERNET_KEY", raising=False)
    # When FERNET_KEY is missing, Settings instantiation must fail with ValidationError
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.anyio
async def test_lifespan_fails_when_fernet_key_unset(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "FERNET_KEY", "")
    test_app = FastAPI()
    with pytest.raises(RuntimeError, match="FERNET_KEY environment variable is required"):
        async with lifespan(test_app):
            pass


@pytest.mark.anyio
async def test_lifespan_fails_when_fernet_key_is_compromised(monkeypatch):
    from app.core.config import settings
    compromised_key = "UAgBIptmb50gZM94VLBKia38mASQ4w-5H6KCS_z7_YM="
    monkeypatch.setattr(settings, "FERNET_KEY", compromised_key)
    test_app = FastAPI()
    with pytest.raises(RuntimeError, match="FERNET_KEY is set to the compromised key"):
        async with lifespan(test_app):
            pass


@pytest.mark.anyio
async def test_lifespan_succeeds_with_fresh_key(monkeypatch):
    from app.core.config import settings
    fresh_key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "FERNET_KEY", fresh_key)
    test_app = FastAPI()
    async with lifespan(test_app):
        assert settings.FERNET_KEY == fresh_key


def test_encryption_module_fails_fast_in_production_without_key(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "ENV", "production")
    monkeypatch.setattr(settings, "FERNET_KEY", "")
    from app.db import encryption
    with pytest.raises(RuntimeError, match="FERNET_KEY environment variable is required in production"):
        encryption._init_fernet()
