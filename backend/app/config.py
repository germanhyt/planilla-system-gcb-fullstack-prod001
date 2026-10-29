from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://planilla:planilla@localhost:5432/planilla"
    redis_url: str = "redis://localhost:6379/0"
    tz: str = "America/Lima"
    jwt_secret: str = "cambiar-en-produccion"
    jwt_minutes: int = 480
    seed_password: str = "Cambiar123!"


settings = Settings()
