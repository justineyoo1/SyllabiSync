import os


def setup_module() -> None:
    os.environ.setdefault("POSTGRES_DSN", "postgresql+psycopg2://user:pass@localhost:5432/db")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
    os.environ.setdefault("S3_ACCESS_KEY", "minioadmin")
    os.environ.setdefault("S3_SECRET_KEY", "minioadmin")
    os.environ.setdefault("S3_BUCKET", "test")


def test_health_live() -> None:
    from fastapi.testclient import TestClient
    from apps.api.main import app

    client = TestClient(app)
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


