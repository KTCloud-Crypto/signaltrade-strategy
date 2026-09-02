from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)
    environment: str = "development"
    database_url: str = "postgresql://signaltrade:signaltrade-local@localhost:5432/signaltrade"
    upbit_api_base_url: str = "https://api.upbit.com"
    upbit_ws_url: str = "wss://api.upbit.com/websocket/v1"
    watch_markets: str = "KRW-BTC,KRW-ETH,KRW-XRP,KRW-SOL,KRW-DOGE,KRW-TRX"
    strategy_refresh_seconds: int = 30

    @property
    def watch_market_list(self) -> list[str]:
        return [value.strip().upper() for value in self.watch_markets.split(",") if value.strip()]


settings = Settings()

