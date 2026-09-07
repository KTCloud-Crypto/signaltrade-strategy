from fastapi.testclient import TestClient

from signaltrade_strategy.main import app

client = TestClient(app)


def test_health_and_ready() -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ready"}


def test_metrics_are_exposed() -> None:
    client.get("/does-not-exist/12345")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "signaltrade_http_requests_total" in response.text
    assert 'route="unmatched"' in response.text
    assert "/does-not-exist/12345" not in response.text
