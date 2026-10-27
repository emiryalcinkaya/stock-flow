from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Eysto", alias="app_name")
    database_url: str = Field(alias="database_url")
    secret_key: str = Field(alias="secret_key", min_length=16)
    algorithm: str = Field(default="HS256", alias="algorithm")
    access_token_expire_minutes: int = Field(default=60, alias="access_token_expire_minutes")

    cors_origins: List[str] = Field(
        default=[
            "http://localhost:5500",
            "http://127.0.0.1:5500",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ],
        alias="cors_origins",
    )
    low_stock_threshold: int = Field(default=5, ge=0, alias="low_stock_threshold")

    login_max_attempts: int = Field(default=5, ge=1, alias="login_max_attempts")
    login_lockout_seconds: int = Field(default=300, ge=1, alias="login_lockout_seconds")

    log_level: str = Field(default="INFO", alias="log_level")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value):
        # Allows a comma separated string in .env: cors_origins=http://a,http://b
        if isinstance(value, str) and not value.strip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
