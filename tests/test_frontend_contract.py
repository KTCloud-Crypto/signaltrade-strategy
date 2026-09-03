from signaltrade_strategy.main import app


def test_frontend_routes_and_strategy_response_contract():
    spec = app.openapi()
    expected = {
        ("get", "/strategies"), ("get", "/strategies/active"),
        ("get", "/strategies/markets"), ("get", "/strategies/markets/tickers"),
        ("get", "/strategies/allocation"), ("get", "/strategies/subscription-events"),
        ("get", "/strategies/signals"), ("put", "/strategies/{strategy_id}/subscription"),
        ("post", "/strategies/{strategy_id}/test-signal"), ("get", "/strategies/reserved"),
    }
    assert all(method in spec["paths"].get(path, {}) for method, path in expected)
    fields = set(spec["components"]["schemas"]["StrategyOut"]["properties"])
    assert fields == {"id", "code", "name", "description", "market", "market_name",
        "timeframe_minutes", "parameters", "default_invest_ratio", "selected", "paused",
        "has_open_position", "invest_ratio", "allocated_amount", "allocation_mode",
        "available_cash", "stop_loss_rate", "take_profit_rate", "selected_timeframe_minutes",
        "allowed_timeframes", "last_evaluated_at", "last_close_price", "last_metrics", "last_action"}
