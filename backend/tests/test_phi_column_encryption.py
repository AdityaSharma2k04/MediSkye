import pytest
from cryptography.fernet import Fernet

from app.db.encryption import EncryptedJSON, EncryptedText

METRICS = [
    {"test": "Hemoglobin", "value": "14.2", "unit": "g/dL", "range": "12.0 - 15.5", "status": "Normal"},
    {"test": "क्रिएटिनिन", "value": "0.9", "unit": "mg/dL", "range": "0.6 - 1.2", "status": "Normal"},
]


def test_text_roundtrip_and_ciphertext():
    t = EncryptedText()
    token = t.process_bind_param("Aditya Sharma", None)
    assert token.startswith("gAAAA") and "Aditya" not in token
    assert t.process_result_value(token, None) == "Aditya Sharma"


@pytest.mark.parametrize("value", ["", "Hemoglobin is normal.", "मरीज का सारांश", "x" * 5000])
def test_text_roundtrip_values(value):
    t = EncryptedText()
    assert t.process_result_value(t.process_bind_param(value, None), None) == value


def test_text_none_and_legacy_plaintext_passthrough():
    t = EncryptedText()
    assert t.process_bind_param(None, None) is None
    assert t.process_result_value(None, None) is None
    assert t.process_result_value("Plain legacy name", None) == "Plain legacy name"


def test_text_undecryptable_token_is_none_not_ciphertext():
    t = EncryptedText()
    foreign = Fernet(Fernet.generate_key()).encrypt(b"secret").decode()
    assert t.process_result_value(foreign, None) is None


def test_json_roundtrip_and_ciphertext():
    j = EncryptedJSON()
    token = j.process_bind_param(METRICS, None)
    assert isinstance(token, str) and token.startswith("gAAAA")
    assert "Hemoglobin" not in token
    assert j.process_result_value(token, None) == METRICS


def test_json_empty_list_none_and_legacy_passthrough():
    j = EncryptedJSON()
    assert j.process_result_value(j.process_bind_param([], None), None) == []
    assert j.process_bind_param(None, None) is None
    assert j.process_result_value(None, None) is None
    assert j.process_result_value(METRICS, None) == METRICS       # legacy list
    assert j.process_result_value({"a": 1}, None) == {"a": 1}     # legacy dict


def test_json_undecryptable_token_is_none():
    j = EncryptedJSON()
    foreign = Fernet(Fernet.generate_key()).encrypt(b"[1]").decode()
    assert j.process_result_value(foreign, None) is None

