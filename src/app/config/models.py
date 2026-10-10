from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

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


class LoggingSettings(ConfigurationModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


class Settings(ConfigurationModel):
    environment: Environment = "local"
    app: ApplicationSettings = ApplicationSettings()
    persistence: PersistenceSettings = PersistenceSettings()
    logging: LoggingSettings = LoggingSettings()
