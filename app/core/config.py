from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import DirectoryPath
from typing import Literal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str
    debug: bool = False
    environment: Literal['dev', 'test', 'prod']
    database_url: str
    allowed_root: DirectoryPath

    model_config = SettingsConfigDict(env_file=BASE_DIR / '.env')


settings = Settings()
