import pytest
from app.core.observability import _before_send


def test_before_send_strips_breadcrumbs_and_pii():
    event = {
        "request": {"url": "https://api.mediskye.com/api/v1/query", "data": "sensitive query"},
        "user": {"id": "123", "email": "patient@test.com"},
        "breadcrumbs": [
            {"category": "xhr", "message": "POST /api/v1/query with patient blood results"},
            {"category": "navigation", "from": "/reports", "to": "/chat"},
        ],
        "extra": {
            "query": "What does high bilirubin mean?",
            "safe_counter": 42,
        },
        "contexts": {
            "clinical": {
                "phi": "Patient has diabetes",
                "status": "active",
            }
        },
        "exception": {
            "values": [
                {"type": "ValueError", "value": "User input failed validation: secret PHI"}
            ]
        },
    }

    scrubbed = _before_send(event)

    assert "request" not in scrubbed
    assert "user" not in scrubbed
    assert "breadcrumbs" not in scrubbed
    assert scrubbed["extra"]["query"] == "[scrubbed]"
    assert scrubbed["extra"]["safe_counter"] == 42
    assert scrubbed["contexts"]["clinical"]["phi"] == "[scrubbed]"
    assert scrubbed["contexts"]["clinical"]["status"] == "active"
    assert scrubbed["exception"]["values"][0]["value"] == "[scrubbed exception message]"
