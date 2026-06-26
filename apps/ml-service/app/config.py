"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """ML Service configuration."""

    environment: str = "development"
    port: int = 8000
    database_url: str = "postgresql://iporadar_readonly:iporadar_dev@localhost:5432/iporadar"

    class Config:
        env_prefix = ""
        case_sensitive = False


settings = Settings()
