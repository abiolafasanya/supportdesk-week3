import pytest

from app import triage


@pytest.fixture(autouse=True)
def no_log_file(monkeypatch):
    """Tests never write to logs/usage.csv."""
    monkeypatch.setattr(triage, "log_usage", lambda *a, **k: None)
