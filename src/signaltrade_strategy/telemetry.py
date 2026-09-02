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
