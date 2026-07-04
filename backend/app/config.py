from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/crypto_research"
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    coingecko_api_key: str | None = None
    openai_api_key: str | None = None
    refresh_token: str | None = None
    cors_origins: str = "http://localhost:3000"
    tracked_asset_count: int = 150
    market_universe_source: str = "binance_futures"
    binance_futures_base_url: str = "https://fapi.binance.com"
    binance_futures_base_urls: str = "https://fapi.binance.com,https://fapi1.binance.com,https://fapi2.binance.com,https://fapi3.binance.com,https://fapi4.binance.com"
    binance_futures_quote_assets: str = "USDT"
    binance_futures_contract_type: str = "PERPETUAL"
    core_technical_symbols: str = "BTC,ETH"
    auto_refresh_enabled: bool = True
    auto_refresh_interval_minutes: int = 30
    market_scan_interval_minutes: int = 15
    candidate_scan_interval_minutes: int = 5
    paper_position_interval_minutes: int = 5
    technical_refresh_interval_minutes: int = 30
    kline_refresh_interval_minutes: int = 15
    candidate_min_opportunity_score: int = 75
    technical_refresh_limit: int = 30
    paper_account_balance: float = 10000
    paper_margin_per_trade: float = 500
    paper_leverage: int = 5
    paper_min_opportunity_score: int = 80
    paper_fee_rate: float = 0.0012

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def core_technical_symbol_list(self) -> set[str]:
        return {symbol.strip().upper() for symbol in self.core_technical_symbols.split(",") if symbol.strip()}

    @property
    def futures_quote_asset_list(self) -> set[str]:
        return {asset.strip().upper() for asset in self.binance_futures_quote_assets.split(",") if asset.strip()}

    @property
    def futures_base_url_list(self) -> list[str]:
        urls = [url.strip().rstrip("/") for url in self.binance_futures_base_urls.split(",") if url.strip()]
        fallback = self.binance_futures_base_url.strip().rstrip("/")
        return list(dict.fromkeys(urls + ([fallback] if fallback else [])))


@lru_cache
def get_settings() -> Settings:
    return Settings()
