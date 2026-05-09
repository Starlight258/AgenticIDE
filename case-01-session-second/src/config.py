from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key"),
    )
    model: str = Field(
        default="claude-sonnet-4-5",
        validation_alias=AliasChoices("MODEL", "ANTHROPIC_MODEL", "model"),
    )
    use_vertex: bool = Field(
        default=False,
        validation_alias=AliasChoices("USE_VERTEX", "use_vertex"),
    )
    db_url: str = Field(
        default="sqlite+aiosqlite:///./sessions.db",
        validation_alias=AliasChoices("DB_URL", "db_url"),
    )
    env: str = Field(
        default="development",
        validation_alias=AliasChoices("ENV", "env"),
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def get_settings() -> Settings:
    return Settings()
