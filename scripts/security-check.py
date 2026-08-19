#!/usr/bin/env python3
"""Repository-level security and consistency checks for API-VPS."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_FILES = {
    "agent/deploy_agent.py",
    "agent/docker-compose.agent.yml",
    "vps_control/api_routes.py",
    "vps_control/file_manager.py",
    "vps_control/terminal.py",
    "vps_control/docker_manager.py",
}

FORBIDDEN_PYTHON_PATTERNS = {
    r"\bshell\s*=\s*True\b": "shell=True is not allowed",
    r"\bsubprocess\.getoutput\s*\(": "subprocess.getoutput is not allowed",
    r"\bos\.system\s*\(": "os.system is not allowed",
    r"APIRouter\s*\(\s*prefix\s*=\s*[\"']/control": (
        "legacy unauthenticated /control router is not allowed"
    ),
}

errors: list[str] = []

for relative in sorted(FORBIDDEN_FILES):
    if (ROOT / relative).exists():
        errors.append(f"obsolete or unsafe file is present: {relative}")

for path in sorted(ROOT.rglob("*.py")):
    if path == Path(__file__).resolve():
        continue
    if any(part in {".git", ".venv", "venv", "__pycache__"} for part in path.parts):
        continue
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(ROOT)
    for pattern, message in FORBIDDEN_PYTHON_PATTERNS.items():
        if re.search(pattern, text):
            errors.append(f"{relative}: {message}")

entrypoint = (ROOT / "app.py").read_text(encoding="utf-8").strip()
if entrypoint != 'from vps_control.app import app\n\n__all__ = ["app"]':
    errors.append("app.py must remain a minimal import-only ASGI entrypoint")

compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
if "${BIND_ADDRESS:-127.0.0.1}:${PORT:-9000}:9000" not in compose:
    errors.append("docker-compose.yml must bind to 127.0.0.1 by default")
if "/var/run/docker.sock:/var/run/docker.sock" not in compose:
    errors.append("docker-compose.yml is missing the Docker socket mount")
if "no-new-privileges:true" not in compose:
    errors.append("docker-compose.yml is missing no-new-privileges")

dashboard = (ROOT / "dashboard/index.html").read_text(encoding="utf-8")
for required in (
    'data-page="overview"',
    'data-page="monitoring"',
    'data-page="files"',
    'data-page="docker"',
    'data-page="deploy"',
    'data-page="backups"',
    'data-page="logs"',
    'data-page="settings"',
):
    if required not in dashboard:
        errors.append(f"dashboard is missing required page marker: {required}")

deploy_workflow = (
    ROOT / ".github/workflows/deploy-vps.yml"
).read_text(encoding="utf-8")
for required in (
    "secrets.VPS_HOST",
    "secrets.VPS_SSH_KEY",
    "StrictHostKeyChecking=yes",
    "scripts/deploy-vps.sh",
):
    if required not in deploy_workflow:
        errors.append(f"deploy workflow is missing: {required}")

tracked_secret_names = {
    ".env",
    "config/projects.json",
    "id_rsa",
    "id_ed25519",
}
for name in tracked_secret_names:
    if (ROOT / name).exists():
        errors.append(f"runtime secret/config must not be tracked: {name}")

if errors:
    print("Security/consistency checks failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("Security/consistency checks passed.")
