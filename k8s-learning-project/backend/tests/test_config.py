from app.core.config import Settings


def test_cors_origins_csv_env(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8080,http://localhost:30080")
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:8080", "http://localhost:30080"]


def test_cors_origins_json_env(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:8080","http://localhost:30080"]')
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:8080", "http://localhost:30080"]
