from app.config import get_settings, health


def test_health():
    assert health()["status"] == "ok"


def test_default_settings_use_small_models(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    assert get_settings("anthropic").model == "claude-haiku-5-5"
