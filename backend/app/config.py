from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/crypto_research"
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    coingecko_api_key: str | None = None
    openai_api_key: str | None = None
    refresh_token: str | None = None
    cors_origins: str = "http://localhost:3000"
    tracked_asset_count: int = 100
    core_technical_symbols: str = "BTC,ETH"
    auto_refresh_enabled: bool = True
    auto_refresh_interval_minutes: int = 30
    paper_account_balance: float = 10000
    paper_margin_per_trade: float = 500
    paper_leverage: int = 5
    paper_min_opportunity_score: int = 80

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def core_technical_symbol_list(self) -> set[str]:
        return {symbol.strip().upper() for symbol in self.core_technical_symbols.split(",") if symbol.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
