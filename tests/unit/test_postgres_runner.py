import subprocess
from unittest.mock import Mock

import pytest

from scripts.test_postgres import main, require_local_docker


def test_runner_rejects_remote_docker_without_contacting_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RuntimeError, match="local Docker socket"):
        require_local_docker({"DOCKER_HOST": "tcp://remote.example:2376"})
    run.assert_not_called()


def test_runner_inspects_context_endpoint_before_starting_containers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="ssh://remote.example\n"))
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(RuntimeError, match="local Docker socket"):
        require_local_docker({"DOCKER_CONTEXT": "remote"})
    assert run.call_args.args[0][:3] == ["docker", "context", "inspect"]


def test_runner_does_not_clean_up_a_rejected_remote_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example:2376")
    monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
    run = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    assert main() == 1
    run.assert_not_called()
