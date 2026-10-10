"""Run PostgreSQL tests against a new local container, then remove that project."""

import os
import secrets
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path


def require_local_docker(environment: Mapping[str, str]) -> None:
    endpoint = environment.get("DOCKER_HOST", "")
    if environment.get("DOCKER_CONTEXT") or not endpoint:
        endpoint = subprocess.run(
            ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
    if not endpoint.startswith(("unix://", "npipe://")):
        raise RuntimeError("PostgreSQL tests require a local Docker socket, not a remote daemon")


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    project_name = "template-api-test-" + secrets.token_hex(6)
    environment = {
        **os.environ,
        "APP_ENV": "test",
        "TEMPLATE_TEST_PROJECT": project_name,
        "TEMPLATE_TEST_PASSWORD": secrets.token_urlsafe(32),
    }
    compose = [
        "docker",
        "compose",
        "-f",
        str(project_root / "compose.test.yml"),
        "-p",
        project_name,
    ]
    result = 1
    project_started = False
    try:
        require_local_docker(environment)
        project_started = True
        subprocess.run(
            [*compose, "up", "--wait", "--wait-timeout", "60"],
            env=environment,
            cwd=project_root,
            check=True,
            timeout=120,
        )
        published_port = subprocess.run(
            [*compose, "port", "postgres-test", "5432"],
            env=environment,
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
        host, port = published_port.rsplit(":", 1)
        if host != "127.0.0.1" or not port.isdecimal():
            raise RuntimeError("Test database must be published on a loopback-only port")
        environment["TEMPLATE_TEST_POSTGRES_PORT"] = port
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-m", "postgres", *sys.argv[1:]],
            env=environment,
            cwd=project_root,
            check=False,
        ).returncode
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        print(f"PostgreSQL runner failed: {error}", file=sys.stderr)
    finally:
        if project_started:
            try:
                subprocess.run(
                    [*compose, "down", "--timeout", "10"],
                    env=environment,
                    cwd=project_root,
                    check=True,
                    timeout=45,
                )
            except (OSError, subprocess.SubprocessError) as error:
                print(
                    f"Could not remove disposable project {project_name}: {error}", file=sys.stderr
                )
                result = 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
