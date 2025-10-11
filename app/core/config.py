from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Zalando Scraper API"
    version: str = "1.0.0"
    debug: bool = False

    # CORS settings
    cors_origins: list = ["*"]

    # Rate limiting
    rate_limit_per_minute: int = 60

    class Config:
        env_file = ".env"


settings = Settings()