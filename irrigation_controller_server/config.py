from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class RelayConfig(BaseModel):
    host: str
    port: int
    unit_id: int
    timeout: int


class BrokerConfig(BaseModel):
    url: str
    result_backend: str
    beat_dburi: str


class Settings(BaseSettings):
    relay: RelayConfig
    broker: BrokerConfig

    model_config = SettingsConfigDict(env_nested_delimiter="__")


@lru_cache
def get_settings() -> Settings:
    return Settings()
