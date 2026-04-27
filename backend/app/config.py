from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://statuser:statpass@localhost:5432/statanalysis"
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "development"
    log_level: str = "INFO"

    # Cache TTL in seconds
    stats_cache_ttl: int = 900  # 15 minutes


settings = Settings()
