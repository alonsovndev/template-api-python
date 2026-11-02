import json
import re
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
)

Environment = Literal["local", "dev", "test", "container", "prod"]


class ConfigurationModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)


class ApplicationSettings(ConfigurationModel):
    name: str = Field(default="template-api-python", min_length=1)
    version: str = Field(default="0.1.0", min_length=1)


class PostgreSQLSettings(ConfigurationModel):
    host: str = ""
    port: int = Field(default=5432, ge=1, le=65535)
    username: str = ""
    password: SecretStr = SecretStr("")
    database: str = ""
    ssl_mode: Literal["disable", "require"] = "disable"
    pool_mode: Literal["queue", "null"] = "queue"

    @model_validator(mode="before")
    @classmethod
    def read_credentials_json(cls, data: Any) -> Any:
        """Accept the {"username", "password"} JSON that AWS Secrets Manager stores for RDS."""
        if not isinstance(data, dict) or "credentials_json" not in data:
            return data
        values = {name: value for name, value in data.items() if name != "credentials_json"}
        raw_credentials = str(data["credentials_json"] or "").strip()
        if not raw_credentials:
            return values
        try:
            credentials = json.loads(raw_credentials)
        except ValueError:
            raise ValueError("credentials_json must be valid JSON") from None
        if not isinstance(credentials, dict) or not all(
            isinstance(credentials.get(name), str) and credentials[name]
            for name in ("username", "password")
        ):
            raise ValueError("credentials_json must contain a username and a password")
        return {**values, "username": credentials["username"], "password": credentials["password"]}


class PersistenceSettings(ConfigurationModel):
    driver: Literal["memory", "postgresql"] = "memory"
    postgres: PostgreSQLSettings = PostgreSQLSettings()

    @model_validator(mode="after")
    def require_postgresql_connection(self) -> Self:
        if self.driver == "postgresql":
            connection_values = (
                self.postgres.host,
                self.postgres.username,
                self.postgres.database,
                self.postgres.password.get_secret_value(),
            )
            if not all(value.strip() for value in connection_values):
                raise ValueError("PostgreSQL host, username, database, and password are required")
        return self


_ORIGIN = re.compile(r"^https?://[^/\s?#]+$")


def _split_origins(value: Any) -> Any:
    if isinstance(value, str):
        return tuple(origin.strip() for origin in value.split(",") if origin.strip())
    return value


class CorsSettings(ConfigurationModel):
    allowed_origins: Annotated[tuple[str, ...], BeforeValidator(_split_origins)] = ()

    @model_validator(mode="after")
    def require_explicit_origins(self) -> Self:
        if not all(_ORIGIN.match(origin) for origin in self.allowed_origins):
            raise ValueError("CORS origins must look like https://host[:port], without a path")
        return self


class LoggingSettings(ConfigurationModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


class Settings(ConfigurationModel):
    environment: Environment = "local"
    app: ApplicationSettings = ApplicationSettings()
    persistence: PersistenceSettings = PersistenceSettings()
    cors: CorsSettings = CorsSettings()
    logging: LoggingSettings = LoggingSettings()
