from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import pytest
from app.services.upload_jobs import is_stale_building

def _doc(status, minutes_old, aware=True):
    created = datetime.now(UTC) - timedelta(minutes=minutes_old)
    if not aware:
        created = created.replace(tzinfo=None)
    return SimpleNamespace(index_status=status, created_at=created)

def test_old_building_doc_is_stale():
    assert is_stale_building(_doc("building", 30))

def test_naive_timestamp_is_treated_as_utc():
    assert is_stale_building(_doc("building", 30, aware=False))

def test_fresh_building_doc_is_not_stale():
    assert not is_stale_building(_doc("building", 2))

@pytest.mark.parametrize("status", ["local_ready", "synced", "failed"])
def test_non_building_docs_are_never_stale(status):
    assert not is_stale_building(_doc(status, 120))

def test_missing_created_at_is_not_stale():
    assert not is_stale_building(SimpleNamespace(index_status="building", created_at=None))
