from fastapi.testclient import TestClient

from signaltrade_strategy.main import app

client = TestClient(app)


def test_health_and_ready() -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}
