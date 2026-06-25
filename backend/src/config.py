from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class RunConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    timeout: int = 30


class LogConfig(BaseModel):
    level: str = "INFO"
    fmt: str = (
        "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s resource.service.name=%(otelServiceName)s] - %(message)s"
    )


class ObservabilityConfig(BaseModel):
    app_name: str = "app-a"
    otlp_grpc_endpoint: str = "localhost:4317"


class PostgresConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    user: str = "user"
    password: str = "change_me"
    db: str = "app"
    echo: bool = False
    echo_pool: bool = False
    pool_size: int = 15
    max_overflow: int = 5
    naming_convention: dict = {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_`%(constraint_name)s`",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }

    @property
    def url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=["config/.env", "config/.env.development"],
        case_sensitive=False,
        env_nested_delimiter="__",
        env_prefix="API__",
    )
    env: str = "development"
    title: str = "Prod FastAPI"
    debug: bool = False
    description: str = "FastAPI monolith template"
    version: str = "v0.1.0"
    run: RunConfig = RunConfig()
    logging: LogConfig = LogConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    postgres: PostgresConfig = PostgresConfig()


settings = Settings()
