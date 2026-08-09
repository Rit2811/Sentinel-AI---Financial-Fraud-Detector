from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment contract for dependency reachability checks."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_url: str = Field(
        default="postgresql://sentinel:sentinel_local_only@postgres:5432/sentinel",
        alias="POSTGRES_URL",
    )
    redis_url: str = Field(
        default="redis://:sentinel_local_only@redis:6379/0",
        alias="REDIS_URL",
    )
    readiness_timeout_seconds: float = Field(default=2.0, alias="READINESS_TIMEOUT_SECONDS")


@lru_cache
def get_settings() -> Settings:
    return Settings()
