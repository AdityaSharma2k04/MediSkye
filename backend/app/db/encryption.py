import logging
import sqlalchemy.types as types
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

logger = logging.getLogger(__name__)
fernet = Fernet(settings.FERNET_KEY.encode() if isinstance(settings.FERNET_KEY, str) else settings.FERNET_KEY)

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
        except (InvalidToken, Exception):
            # If decryption fails (e.g., data was already in DB unencrypted), log and return as is
            logger.warning("Fernet decryption failed; falling back to raw database value.")
            return value
