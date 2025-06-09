from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from irrigation_controller_server.models import ZoneType


class BrokerConfig(BaseModel):
    url: str
    result_backend: str
    beat_dburi: str


class RelayConfig(BaseModel):
    host: str
    port: int
    unit_id: int
    timeout: int


class ZoneConfig(BaseModel):
    relay_id: str
    relay_output: int


class Settings(BaseSettings):
    celery_conf: str
    broker: BrokerConfig
    relays: dict[str, RelayConfig]
    zones: dict[ZoneType, ZoneConfig]
    model_config = SettingsConfigDict(env_nested_delimiter="__")


@lru_cache
def get_settings() -> Settings:
    return Settings()
