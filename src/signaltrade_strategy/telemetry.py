import time

from fastapi import Request
from prometheus_client import Counter, Gauge, Histogram


EXTERNAL_REQUESTS = Counter(
    "signaltrade_external_requests_total",
    "External API requests",
    ["provider", "operation", "outcome"],
)
EXTERNAL_DURATION = Histogram(
    "signaltrade_external_request_duration_seconds",
    "External API latency",
    ["provider", "operation"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
WEBSOCKET_CONNECTIONS = Gauge(
    "signaltrade_websocket_connected", "WebSocket connection state", ["provider"]
)
WEBSOCKET_RECONNECTS = Counter(
    "signaltrade_websocket_reconnections_total",
    "WebSocket reconnect attempts",
    ["provider"],
)
MARKET_LAST_TICK = Gauge(
    "signaltrade_market_stream_last_tick_timestamp_seconds",
    "Last market tick Unix timestamp",
    ["market"],
)
STRATEGY_SIGNALS = Counter(
    "signaltrade_strategy_signals_total",
    "Generated strategy signals",
    ["strategy", "market", "action", "source"],
)
HTTP_REQUESTS = Counter("signaltrade_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_DURATION = Histogram("signaltrade_http_request_duration_seconds", "HTTP request latency", ["method", "route"])
HTTP_IN_PROGRESS = Gauge("signaltrade_http_requests_in_progress", "Currently running HTTP requests")


def instrument_http(app) -> None:
    @app.middleware("http")
    async def observe_request(request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        started = time.perf_counter()
        HTTP_IN_PROGRESS.inc()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            HTTP_REQUESTS.labels(request.method, route, str(status)).inc()
            HTTP_DURATION.labels(request.method, route).observe(time.perf_counter() - started)
            HTTP_IN_PROGRESS.dec()
