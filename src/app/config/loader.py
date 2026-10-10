import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, get_args

import yaml
from dotenv import dotenv_values
from pydantic import ValidationError

from app.config.models import Environment, Settings
from app.config.secrets import read_secret_string

_PROFILES_WITH_CREDENTIALS = {"dev", "container", "prod"}
_ENVIRONMENT_VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")


class ConfigurationError(ValueError):
    """Configuration could not be loaded; messages omit configuration values."""


@dataclass(frozen=True)
class ConfigurationPaths:
    config_directory: Path = field(default_factory=lambda: Path(__file__).resolve().parent)
    environment_file: Path = field(default_factory=lambda: Path.cwd() / ".env")


def _parse_yaml(content: str, environment: Mapping[str, str]) -> Any:
    class EnvironmentLoader(yaml.SafeLoader):
        pass

    def resolve_environment(loader: yaml.SafeLoader, node: yaml.ScalarNode) -> str:
        scalar = loader.construct_scalar(node)

        def substitute(match: re.Match[str]) -> str:
            variable_name, default = match.groups()
            if variable_name in environment:
                return environment[variable_name]
            if default is not None:
                return default
            raise ConfigurationError(f"Missing environment variable: {variable_name}")

        if "${" in _ENVIRONMENT_VARIABLE.sub("", scalar):
            raise ConfigurationError("Malformed environment interpolation")
        return _ENVIRONMENT_VARIABLE.sub(substitute, scalar)

    EnvironmentLoader.add_constructor("!ENV", resolve_environment)
    return yaml.load(content, Loader=EnvironmentLoader)


def load_settings(
    paths: ConfigurationPaths | None = None,
    environ: Mapping[str, str] | None = None,
    secret_reader: Callable[[str], str] = read_secret_string,
) -> Settings:
    paths = paths or ConfigurationPaths()
    process_environment = dict(os.environ if environ is None else environ)
    file_environment: dict[str, str] = {}
    if process_environment.get("APP_ENV", "").strip().lower() != "prod":
        try:
            file_environment = {
                name: value
                for name, value in dotenv_values(paths.environment_file, interpolate=False).items()
                if value is not None
            }
        except (OSError, UnicodeError):
            raise ConfigurationError("Could not read the environment file") from None

    environment = file_environment | process_environment
    profile = environment.get("APP_ENV", "local").strip().lower()
    if profile not in get_args(Environment):
        raise ConfigurationError("APP_ENV must be local, dev, test, container, or prod")
    if profile == "prod":
        environment = process_environment

    secret_arn = environment.get("POSTGRES_CREDENTIALS_SECRET_ARN", "").strip()
    uses_credentials = (
        profile in _PROFILES_WITH_CREDENTIALS
        and environment.get("PERSISTENCE_DRIVER", "postgresql").strip().lower() != "memory"
    )
    if (
        secret_arn
        and uses_credentials
        and not environment.get("POSTGRES_CREDENTIALS_JSON", "").strip()
    ):
        try:
            environment = {**environment, "POSTGRES_CREDENTIALS_JSON": secret_reader(secret_arn)}
        except Exception as error:
            raise ConfigurationError(
                f"Could not read the database credentials secret ({type(error).__name__})"
            ) from None

    try:
        content = (paths.config_directory / f"config_{profile}.yml").read_text(encoding="utf-8")
        values = _parse_yaml(content, environment)
    except (OSError, UnicodeError, yaml.YAMLError):
        raise ConfigurationError(
            f"Could not read valid configuration for profile {profile}"
        ) from None

    if not isinstance(values, dict):
        raise ConfigurationError("Configuration must contain a YAML mapping")
    if "environment" in values:
        raise ConfigurationError("Select the environment with APP_ENV, not a YAML field")
    try:
        return Settings.model_validate({**values, "environment": profile})
    except ValidationError as error:
        invalid_fields = ", ".join(
            ".".join(str(part) for part in issue["loc"]) or "settings"
            for issue in error.errors(include_input=False, include_context=False)
        )
        raise ConfigurationError(f"Invalid configuration fields: {invalid_fields}") from None
