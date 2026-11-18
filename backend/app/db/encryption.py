import json
import logging
from typing import Optional
import sqlalchemy.types as types
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

logger = logging.getLogger(__name__)


def _init_fernet() -> Fernet:
    key = getattr(settings, "FERNET_KEY", None)
    is_prod = (
        getattr(settings, "is_production", False)
        or str(getattr(settings, "ENVIRONMENT", "")).lower() in ("production", "prod")
        or str(getattr(settings, "ENV", "")).lower() in ("production", "prod")
    )
    if not key or not str(key).strip():
        if is_prod:
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: FERNET_KEY environment variable is required in production. "
                "Data encryption cannot proceed without a valid key."
            )
        logger.warning("FERNET_KEY is unset in non-production mode; generating ephemeral test key.")
        key = Fernet.generate_key()
    elif isinstance(key, str):
        key = key.encode("utf-8")
    try:
        return Fernet(key)
    except Exception as e:
        if is_prod:
            raise RuntimeError(f"CRITICAL SECURITY CONFIGURATION ERROR: Invalid FERNET_KEY in production: {e}") from e
        logger.warning("Invalid FERNET_KEY in non-production mode; falling back to ephemeral test key: %s", e)
        return Fernet(Fernet.generate_key())


fernet = _init_fernet()


class DataDecryptionError(RuntimeError):
    pass


class EncryptedString(types.TypeDecorator):
    """
    A SQLAlchemy TypeDecorator that encrypts strings before saving to the database
    and decrypts them upon retrieval.
    """
    impl = types.String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, str):
            value = str(value)
        # Encrypt the string
        encrypted = fernet.encrypt(value.encode('utf-8'))
        return encrypted.decode('utf-8')

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        try:
            # Decrypt the string
            decrypted = fernet.decrypt(value.encode('utf-8'))
            return decrypted.decode('utf-8')
        except (InvalidToken, Exception) as exc:
            if isinstance(value, str) and value.startswith("gAAAAA"):
                logger.error("EncryptedString: Fernet-looking value could not be decrypted (wrong key or corruption).")
                raise DataDecryptionError("Corrupted or undecryptable Fernet ciphertext token") from exc
            # If decryption fails (e.g., data was already in DB unencrypted), log and return as is
            logger.warning("Fernet decryption failed; falling back to raw database value.")
            return value


_TOKEN_PREFIX = "gAAAAA"


def _looks_like_token(value) -> bool:
    return isinstance(value, str) and value.startswith(_TOKEN_PREFIX)


def _try_decrypt(value: str) -> Optional[str]:
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except Exception:
        return None


class EncryptedText(types.TypeDecorator):
    """Text encrypted at rest. Legacy plaintext rows still read fine until backfilled.
    A value that looks like a Fernet token but cannot be decrypted (wrong key / corruption)
    raises DataDecryptionError; it is never returned as ciphertext or overwritten with None."""

    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, str):
            value = str(value)
        return fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        try:
            decrypted = fernet.decrypt(value.encode("utf-8")).decode("utf-8")
            return decrypted
        except (InvalidToken, Exception) as exc:
            if isinstance(value, str) and value.startswith("gAAAAA"):
                logger.error("EncryptedText: Fernet-looking value could not be decrypted (wrong key or corruption).")
                raise DataDecryptionError("Corrupted or undecryptable Fernet ciphertext token") from exc
            return value  # legacy plaintext row, not yet backfilled


class EncryptedJSON(types.TypeDecorator):
    """JSON encrypted at rest. The encrypted token is stored as a JSON *string* in the existing JSON column,
    so no schema change is needed. Legacy rows (a JSON list/dict) still read fine until backfilled."""

    impl = types.JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return fernet.encrypt(payload.encode("utf-8")).decode("utf-8")

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                decrypted = fernet.decrypt(value.encode("utf-8")).decode("utf-8")
                try:
                    return json.loads(decrypted)
                except ValueError:
                    logger.error("EncryptedJSON: decrypted payload is not valid JSON.")
                    return None
            except (InvalidToken, Exception) as exc:
                if isinstance(value, str) and value.startswith("gAAAAA"):
                    logger.error("EncryptedJSON: Fernet-looking value could not be decrypted (wrong key or corruption).")
                    raise DataDecryptionError("Corrupted or undecryptable Fernet ciphertext token") from exc
                try:
                    return json.loads(value)
                except ValueError:
                    return value
        return value  # legacy plaintext list/dict
