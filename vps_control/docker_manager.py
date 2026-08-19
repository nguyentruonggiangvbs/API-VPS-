"""Docker management helpers for API-VPS Control Center.

This module keeps Docker operations isolated from FastAPI routes.
"""

import subprocess


def _run(command: list[str]):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "success": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def list_containers():
    return _run([
        "docker",
        "ps",
        "--format",
        "{{.Names}}|{{.Status}}|{{.Ports}}",
    ])


def restart_container(name: str):
    return _run(["docker", "restart", name])


def stop_container(name: str):
    return _run(["docker", "stop", name])


def start_container(name: str):
    return _run(["docker", "start", name])


def logs_container(name: str):
    return _run(["docker", "logs", "--tail", "200", name])
