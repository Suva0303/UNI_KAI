from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    @field_validator("database_url")
    @classmethod
    def database_must_be_uni(cls, v: str) -> str:
        """Имя базы в URL должно быть `uni`."""
        v = (v or "").strip()
        if not v:
            raise ValueError("DATABASE_URL не задан.")
        try:
            parsed = make_url(v)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Некорректный DATABASE_URL: {exc}") from exc
        db_name = (parsed.database or "").strip()
        if db_name.lower() != "uni":
            raise ValueError(
                "Разрешена только база данных UNI. "
                f"В DATABASE_URL указано имя «{db_name or '(пусто)'}». "
                "Задайте, например: postgresql+asyncpg://user:pass@localhost:5432/UNI"
            )
        return v
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 240
    admin_login: str
    admin_password: str
    auto_bootstrap_dashboard: bool = False


settings = Settings()
