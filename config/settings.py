from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EASICOIN_", case_sensitive=False)

    api_base_url: str = Field(default="https://api.easicoin.io")
    ws_base_url: str = Field(default="wss://ws.easicoin.io")
    api_key: str = Field(default="")
    api_secret: str = Field(default="")
    request_timeout: float = Field(default=10.0)


settings = AppSettings()
