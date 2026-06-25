from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.constants import Environment


class RunConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    timeout: int = 30


class LogConfig(BaseModel):
    level: str = "INFO"
    fmt: str = (
        "[%(asctime)s.%(msecs)03d] %(module)20s:%(lineno)-3d %(levelname)-8s - %(message)s"
    )
    fmt_otlp: str = (
        "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s resource.service.name=%(otelServiceName)s] - %(message)s"
    )


class ObservabilityConfig(BaseModel):
    app_name: str
    otlp_grpc_endpoint: str


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
    env: Environment = Environment.development
    title: str = "Prod FastAPI"

    @property
    def observability_enabled(self) -> bool:
        return self.env != Environment.development and self.observability is not None

    debug: bool = False
    description: str = "FastAPI monolith template"
    version: str = "v0.1.0"
    run: RunConfig = RunConfig()
    logging: LogConfig = LogConfig()
    observability: ObservabilityConfig | None = None
    postgres: PostgresConfig = PostgresConfig()


settings = Settings()
