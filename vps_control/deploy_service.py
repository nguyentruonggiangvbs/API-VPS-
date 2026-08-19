from __future__ import annotations

import json
import os
import selectors
import shlex
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .audit import audit_log
from .config import settings
from .file_service import FileServiceError, file_service
from .jobs import job_store


class DeployServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    root: str
    path: str
    branch: str
    repository: str | None
    mode: str
    compose_file: str | None
    health_url: str | None
    enabled: bool
    protected: bool
    allow_dirty: bool
    commands: tuple[tuple[str, ...], ...]
    timeout_seconds: int


class DeployService:
    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def list_projects(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for project in self._load_projects():
            status = self._project_status(project)
            rows.append(
                {
                    "id": project.id,
                    "name": project.name,
                    "root": project.root,
                    "path": project.path,
                    "branch": project.branch,
                    "repository": project.repository,
                    "mode": project.mode,
                    "enabled": project.enabled,
                    "protected": project.protected,
                    "health_url": project.health_url,
                    "status": status,
                }
            )
        return rows

    def get_project(self, project_id: str) -> Project:
        for project in self._load_projects():
            if project.id == project_id:
                return project
        raise DeployServiceError("Không tìm thấy dự án")

    def deploy(
        self,
        project_id: str,
        *,
        actor: str,
        client_ip: str,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        if not project.enabled:
            raise DeployServiceError("Dự án chưa được bật triển khai")
        if project.protected:
            raise DeployServiceError(
                "Dự án này được bảo vệ và không thể tự triển khai từ API"
            )

        lock = self._project_lock(project.id)
        if lock.locked():
            raise DeployServiceError("Dự án đang có một tác vụ triển khai khác")

        job = job_store.create(
            kind="deploy",
            target=project.id,
            metadata={
                "name": project.name,
                "branch": project.branch,
                "mode": project.mode,
            },
        )
        thread = threading.Thread(
            target=self._deploy_worker,
            args=(project, job["id"], lock, actor, client_ip),
            daemon=True,
            name=f"deploy-{project.id}",
        )
        thread.start()
        return job

    def _deploy_worker(
        self,
        project: Project,
        job_id: str,
        lock: threading.Lock,
        actor: str,
        client_ip: str,
    ) -> None:
        previous_sha: str | None = None
        project_dir: Path | None = None
        with lock:
            try:
                job_store.update(
                    job_id,
                    state="running",
                    message="Đang triển khai",
                    started=True,
                )
                project_dir = self._project_dir(project)
                job_store.log(job_id, f"Thư mục dự án: {project_dir}")

                if (project_dir / ".git").exists():
                    previous_sha = self._run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=project_dir,
                        timeout=30,
                        job_id=job_id,
                    ).strip()
                    dirty = self._run(
                        ["git", "status", "--porcelain"],
                        cwd=project_dir,
                        timeout=30,
                        job_id=job_id,
                    ).strip()
                    if dirty and not project.allow_dirty:
                        raise DeployServiceError(
                            "Dự án có thay đổi chưa commit; đã dừng để tránh mất dữ liệu"
                        )

                    job_store.log(
                        job_id,
                        f"Đang đồng bộ nhánh {project.branch}",
                    )
                    self._run(
                        ["git", "fetch", "--prune", "origin", project.branch],
                        cwd=project_dir,
                        timeout=180,
                        job_id=job_id,
                    )
                    self._run(
                        ["git", "checkout", project.branch],
                        cwd=project_dir,
                        timeout=60,
                        job_id=job_id,
                    )
                    self._run(
                        ["git", "merge", "--ff-only", f"origin/{project.branch}"],
                        cwd=project_dir,
                        timeout=180,
                        job_id=job_id,
                    )
                else:
                    raise DeployServiceError(
                        "Thư mục dự án chưa phải Git repository"
                    )

                if project.mode == "compose":
                    self._deploy_compose(project, project_dir, job_id)
                elif project.mode == "commands":
                    self._deploy_commands(project, project_dir, job_id)
                else:
                    raise DeployServiceError(
                        f"Chế độ triển khai không được hỗ trợ: {project.mode}"
                    )

                self._health_check(project, job_id)
                current_sha = self._run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=project_dir,
                    timeout=30,
                    job_id=job_id,
                ).strip()
                result = {
                    "previous_sha": previous_sha,
                    "current_sha": current_sha,
                }
                job_store.update(
                    job_id,
                    state="success",
                    message="Triển khai thành công",
                    result=result,
                    finished=True,
                )
                job_store.log(job_id, "Triển khai hoàn tất")
                audit_log.write(
                    action="deploy.project",
                    outcome="success",
                    actor=actor,
                    client_ip=client_ip,
                    details={
                        "project": project.id,
                        "job_id": job_id,
                        **result,
                    },
                )
            except Exception as exc:
                job_store.log(job_id, f"LỖI: {exc}")
                rolled_back = False
                rollback_error: str | None = None
                if previous_sha and project_dir:
                    try:
                        job_store.log(
                            job_id,
                            f"Đang rollback về {previous_sha}",
                        )
                        self._run(
                            ["git", "reset", "--hard", previous_sha],
                            cwd=project_dir,
                            timeout=120,
                            job_id=job_id,
                        )
                        if project.mode == "compose":
                            self._deploy_compose(project, project_dir, job_id)
                        elif project.mode == "commands":
                            self._deploy_commands(project, project_dir, job_id)
                        rolled_back = True
                        job_store.log(job_id, "Rollback hoàn tất")
                    except Exception as rollback_exc:
                        rollback_error = str(rollback_exc)
                        job_store.log(
                            job_id,
                            f"ROLLBACK LỖI: {rollback_error}",
                        )

                state = "rolled_back" if rolled_back else "failed"
                message = (
                    "Triển khai lỗi; đã khôi phục phiên bản trước"
                    if rolled_back
                    else "Triển khai thất bại"
                )
                job_store.update(
                    job_id,
                    state=state,
                    message=message,
                    result={
                        "error": str(exc),
                        "rolled_back": rolled_back,
                        "rollback_error": rollback_error,
                        "previous_sha": previous_sha,
                    },
                    finished=True,
                )
                audit_log.write(
                    action="deploy.project",
                    outcome=state,
                    actor=actor,
                    client_ip=client_ip,
                    details={
                        "project": project.id,
                        "job_id": job_id,
                        "error": str(exc),
                        "rollback_error": rollback_error,
                    },
                )

    def _deploy_compose(
        self,
        project: Project,
        project_dir: Path,
        job_id: str,
    ) -> None:
        compose_file = project.compose_file or "docker-compose.yml"
        compose_path = project_dir / compose_file
        if not compose_path.is_file():
            raise DeployServiceError(
                f"Không tìm thấy compose file: {compose_file}"
            )

        command = self._compose_command()
        command.extend(
            [
                "-f",
                str(compose_path),
                "up",
                "-d",
                "--build",
                "--remove-orphans",
            ]
        )
        job_store.log(job_id, "Đang build và khởi động Docker Compose")
        self._run(
            command,
            cwd=project_dir,
            timeout=project.timeout_seconds,
            job_id=job_id,
        )

    def _deploy_commands(
        self,
        project: Project,
        project_dir: Path,
        job_id: str,
    ) -> None:
        if not project.commands:
            raise DeployServiceError(
                "Dự án chưa cấu hình lệnh triển khai"
            )
        replacements = {
            "{project_dir}": str(project_dir),
            "{branch}": project.branch,
            "{project_id}": project.id,
        }
        for original in project.commands:
            command = [
                self._replace_tokens(argument, replacements)
                for argument in original
            ]
            self._validate_command(command)
            job_store.log(
                job_id,
                "Chạy: " + " ".join(shlex.quote(item) for item in command),
            )
            self._run(
                command,
                cwd=project_dir,
                timeout=project.timeout_seconds,
                job_id=job_id,
            )

    def _health_check(self, project: Project, job_id: str) -> None:
        if not project.health_url:
            job_store.log(job_id, "Dự án không cấu hình health check")
            return

        job_store.log(
            job_id,
            f"Đang kiểm tra sức khỏe: {project.health_url}",
        )
        deadline = time.monotonic() + 90
        last_error = "unknown"
        while time.monotonic() < deadline:
            try:
                request = urllib.request.Request(
                    project.health_url,
                    headers={
                        "User-Agent": "api-vps-health/1.0",
                        "Cache-Control": "no-cache",
                    },
                )
                with urllib.request.urlopen(request, timeout=10) as response:
                    if 200 <= response.status < 400:
                        job_store.log(
                            job_id,
                            f"Health check OK ({response.status})",
                        )
                        return
                    last_error = f"HTTP {response.status}"
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = str(exc)
            time.sleep(4)

        raise DeployServiceError(
            f"Health check thất bại: {last_error}"
        )

    def _project_status(self, project: Project) -> dict[str, Any]:
        try:
            project_dir = self._project_dir(project)
        except DeployServiceError as exc:
            return {
                "available": False,
                "error": str(exc),
            }

        if not (project_dir / ".git").exists():
            return {
                "available": False,
                "path": str(project_dir),
                "error": "Không phải Git repository",
            }

        try:
            current_sha = self._run_quiet(
                ["git", "rev-parse", "HEAD"],
                cwd=project_dir,
                timeout=10,
            ).strip()
            branch = self._run_quiet(
                ["git", "branch", "--show-current"],
                cwd=project_dir,
                timeout=10,
            ).strip()
            dirty = bool(
                self._run_quiet(
                    ["git", "status", "--porcelain"],
                    cwd=project_dir,
                    timeout=10,
                ).strip()
            )
            return {
                "available": True,
                "path": str(project_dir),
                "current_sha": current_sha,
                "branch": branch,
                "dirty": dirty,
            }
        except Exception as exc:
            return {
                "available": False,
                "path": str(project_dir),
                "error": str(exc),
            }

    def _load_projects(self) -> list[Project]:
        path = settings.projects_file
        if not path.is_file():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DeployServiceError(
                f"Không đọc được projects.json: {exc}"
            ) from exc
        if not isinstance(payload, list):
            raise DeployServiceError("projects.json phải là một mảng")

        projects: list[Project] = []
        seen: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                raise DeployServiceError(
                    "Mỗi dự án trong projects.json phải là object"
                )
            project_id = str(item.get("id", "")).strip()
            if (
                not project_id
                or not project_id.replace("-", "").replace("_", "").isalnum()
                or project_id in seen
            ):
                raise DeployServiceError(
                    f"Project id không hợp lệ hoặc trùng: {project_id!r}"
                )
            seen.add(project_id)

            raw_commands = item.get("commands") or []
            commands: list[tuple[str, ...]] = []
            for command in raw_commands:
                if (
                    not isinstance(command, list)
                    or not command
                    or not all(isinstance(arg, str) for arg in command)
                ):
                    raise DeployServiceError(
                        f"commands của {project_id} phải là mảng các mảng chuỗi"
                    )
                commands.append(tuple(command))

            projects.append(
                Project(
                    id=project_id,
                    name=str(item.get("name") or project_id),
                    root=str(item.get("root") or "opt"),
                    path=str(item.get("path") or project_id),
                    branch=str(item.get("branch") or "main"),
                    repository=(
                        str(item["repository"])
                        if item.get("repository")
                        else None
                    ),
                    mode=str(item.get("mode") or "compose"),
                    compose_file=(
                        str(item["compose_file"])
                        if item.get("compose_file")
                        else None
                    ),
                    health_url=(
                        str(item["health_url"])
                        if item.get("health_url")
                        else None
                    ),
                    enabled=bool(item.get("enabled", True)),
                    protected=bool(item.get("protected", False)),
                    allow_dirty=bool(item.get("allow_dirty", False)),
                    commands=tuple(commands),
                    timeout_seconds=min(
                        max(int(item.get("timeout_seconds", 900)), 30),
                        3600,
                    ),
                )
            )
        return projects

    @staticmethod
    def _replace_tokens(
        value: str,
        replacements: dict[str, str],
    ) -> str:
        result = value
        for token, replacement in replacements.items():
            result = result.replace(token, replacement)
        return result

    @staticmethod
    def _validate_command(command: list[str]) -> None:
        allowed = {
            "docker",
            "docker-compose",
            "npm",
            "npx",
            "pnpm",
            "yarn",
            "rsync",
            "cp",
            "mkdir",
        }
        executable = Path(command[0]).name
        if executable not in allowed:
            raise DeployServiceError(
                f"Lệnh {executable!r} không nằm trong allowlist"
            )

    @staticmethod
    def _compose_command() -> list[str]:
        for command in (["docker", "compose"], ["docker-compose"]):
            try:
                subprocess.run(
                    [*command, "version"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                return list(command)
            except (OSError, subprocess.SubprocessError):
                continue
        raise DeployServiceError(
            "Không tìm thấy Docker Compose CLI trong container API-VPS"
        )

    @staticmethod
    def _run(
        command: list[str],
        *,
        cwd: Path,
        timeout: int,
        job_id: str,
    ) -> str:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=DeployService._command_env(),
            bufsize=1,
        )
        output: list[str] = []
        start = time.monotonic()
        assert process.stdout is not None
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while True:
                if time.monotonic() - start > timeout:
                    process.kill()
                    raise DeployServiceError(
                        f"Lệnh quá thời gian {timeout} giây"
                    )

                events = selector.select(timeout=1)
                for key, _ in events:
                    line = key.fileobj.readline()
                    if line:
                        output.append(line)
                        job_store.log(job_id, line.rstrip())

                if process.poll() is not None:
                    remaining = process.stdout.read()
                    if remaining:
                        output.append(remaining)
                        for extra in remaining.splitlines():
                            job_store.log(job_id, extra)
                    break

            if process.returncode != 0:
                raise DeployServiceError(
                    f"Lệnh trả mã lỗi {process.returncode}"
                )
        finally:
            selector.close()
            if process.poll() is None:
                process.kill()
        return "".join(output)

    @staticmethod
    def _run_quiet(
        command: list[str],
        *,
        cwd: Path,
        timeout: int,
    ) -> str:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=DeployService._command_env(),
        )
        return result.stdout

    @staticmethod
    def _command_env() -> dict[str, str]:
        environment = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "COMPOSE_INTERACTIVE_NO_CLI": "1",
        }
        if os.getenv("GIT_HTTP_TOKEN"):
            environment["GIT_ASKPASS"] = "/usr/local/bin/api-vps-git-askpass"
        return environment

    @staticmethod
    def _project_dir(project: Project) -> Path:
        try:
            _, path = file_service.resolve(
                project.root,
                project.path,
                must_exist=True,
            )
        except FileServiceError as exc:
            raise DeployServiceError(str(exc)) from exc
        if not path.is_dir():
            raise DeployServiceError("Đường dẫn dự án không phải thư mục")
        return path

    def _project_lock(self, project_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(project_id, threading.Lock())


deploy_service = DeployService()
