from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_host: str = "db"
    db_port: int = 3306
    db_name: str = "wheelbarrow"
    db_user: str = "wheelbarrow"
    db_password: str = ""
    secret_key: str = "changeme"
    game_tick_ms: int = 100
    resource_tick_s: int = 5
    persist_interval_s: int = 10

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
