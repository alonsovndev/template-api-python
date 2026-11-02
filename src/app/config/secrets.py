import importlib
import re
from typing import Any

_SECRET_ARN = re.compile(r"^arn:[^:]+:secretsmanager:([a-z0-9-]+):[0-9]{12}:secret:[^:]+$")


def read_secret_string(secret_arn: str) -> str:
    """Read one AWS Secrets Manager secret; requires the optional `aws` extra (boto3)."""
    match = _SECRET_ARN.match(secret_arn)
    if match is None:
        raise ValueError("Invalid secret ARN")
    boto3: Any = importlib.import_module("boto3")
    botocore_config: Any = importlib.import_module("botocore.config")
    # Short timeouts keep a blocked network from outlasting Lambda's initialization limit.
    client = boto3.client(
        "secretsmanager",
        region_name=match.group(1),
        config=botocore_config.Config(
            connect_timeout=2, read_timeout=3, retries={"max_attempts": 2}
        ),
    )
    secret_string = client.get_secret_value(SecretId=secret_arn).get("SecretString")
    if not isinstance(secret_string, str) or not secret_string:
        raise ValueError("Secret has no string value")
    return secret_string
