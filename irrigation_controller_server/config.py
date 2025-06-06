from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings


class RelayConfig(BaseModel):
    host: str
    port: int
    unit_id: int
    timeout: int


class Settings(BaseSettings):
    relay: RelayConfig


@lru_cache
def get_settings() -> Settings:
    return Settings()
