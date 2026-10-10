import sys
from types import ModuleType
from typing import Any

import pytest

from app.config.secrets import read_secret_string

SECRET_ARN = "arn:aws:secretsmanager:eu-west-1:123456789012:secret:app-database-AbCdEf"


def install_fake_boto3(monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]) -> list[Any]:
    calls: list[Any] = []

    class FakeClient:
        def get_secret_value(self, **arguments: str) -> dict[str, Any]:
            calls.append(arguments)
            return response

    def create_client(service: str, region_name: str, config: Any) -> FakeClient:
        calls.append((service, region_name))
        calls.append(config.options)
        return FakeClient()

    class FakeConfig:
        def __init__(self, **options: Any) -> None:
            self.options = options

    module = ModuleType("boto3")
    module.client = create_client  # type: ignore[attr-defined]
    botocore = ModuleType("botocore")
    botocore_config = ModuleType("botocore.config")
    botocore_config.Config = FakeConfig  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", module)
    monkeypatch.setitem(sys.modules, "botocore", botocore)
    monkeypatch.setitem(sys.modules, "botocore.config", botocore_config)
    return calls


def test_reads_the_secret_string_in_the_region_of_the_arn(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = install_fake_boto3(monkeypatch, {"SecretString": "value"})
    assert read_secret_string(SECRET_ARN) == "value"
    assert calls == [
        ("secretsmanager", "eu-west-1"),
        {"connect_timeout": 2, "read_timeout": 3, "retries": {"max_attempts": 2}},
        {"SecretId": SECRET_ARN},
    ]


def test_rejects_a_malformed_arn_before_calling_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = install_fake_boto3(monkeypatch, {"SecretString": "value"})
    with pytest.raises(ValueError, match="Invalid secret ARN"):
        read_secret_string("not-an-arn")
    assert calls == []


@pytest.mark.parametrize("response", [{}, {"SecretBinary": b"x"}, {"SecretString": ""}])
def test_rejects_a_secret_without_a_string_value(
    monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]
) -> None:
    install_fake_boto3(monkeypatch, response)
    with pytest.raises(ValueError, match="no string value"):
        read_secret_string(SECRET_ARN)
