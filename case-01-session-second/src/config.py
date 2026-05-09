from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    model: str = "claude-sonnet-4-5"
    use_vertex: bool = False
    db_url: str = "sqlite+aiosqlite:///./sessions.db"
    env: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def get_settings() -> Settings:
    return Settings()
