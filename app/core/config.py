from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    app_name: str
    debug: bool = False
    environment: Literal['dev','test','prod']
    database_url: str

    model_config = SettingsConfigDict(env_file=".env")
