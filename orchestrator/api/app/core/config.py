from functools import lru_cache
from os import getenv


class Settings:
    def __init__(self) -> None:
        self.database_url = getenv("DATABASE_URL", "sqlite:///./data/app.db")


@lru_cache
def get_settings() -> Settings:
    return Settings()
