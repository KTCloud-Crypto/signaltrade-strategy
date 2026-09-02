from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    environment: str = "development"
    database_url: str = "postgresql://signaltrade:signaltrade-local@localhost:5432/signaltrade"
    upbit_api_base_url: str = "https://api.upbit.com"
    upbit_ws_url: str = "wss://api.upbit.com/websocket/v1"
    watch_markets: str = "KRW-BTC,KRW-ETH,KRW-XRP,KRW-SOL,KRW-DOGE,KRW-TRX"
    strategy_refresh_seconds: int = 30
    aws_region: str = "ap-northeast-2"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    sqs_endpoint_url: str | None = None
    sqs_strategy_command_queue_name: str = "signaltrade-strategy-commands"
    sqs_strategy_visibility_timeout_seconds: int = 60
    metrics_enabled: bool = True
    worker_metrics_port: int = 9101
    internal_service_token: str = ""

    @property
    def watch_market_list(self) -> list[str]:
        return [value.strip().upper() for value in self.watch_markets.split(",") if value.strip()]


settings = Settings()
